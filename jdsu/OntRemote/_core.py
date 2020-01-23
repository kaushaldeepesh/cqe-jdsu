# -*- coding: utf-8 -*-
"""
OntRemote Control package

Copyright (c) 2015 - 2019, VIAVI Solutions Inc.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

$Date: 2019-05-15 14:16:30 +0200 (Mi, 15 Mai 2019) $

"""

from time import sleep

from ._base import _OntTcpConnection
from ._error import OntRemoteError
from ._meas import Measurement
from ._application import Application
from ._protection import Protection
from ._cfp2 import Cfp2
from ._vtm import VtmConfiguration
from .util import parseVersionInfo


class OntRemote:
    """Remote Control of an ONT measurement port."""

    def __init__(self, ipAddress, ontPort):
        """
        ipAddress: IP Address of the LEC module or HEC mainframe
        ontPort:   ONT measurement port: '/0/SlotNo/PortNo' (e.g. '/0/4/1')
        """
        
        self._isConnected = False
        self.timeout = 30.0
        """Default timeout for receiveSCPI queries"""
        self.application = Application(self)
        """Application control functions"""
        self.measurement = Measurement(self)
        """Measurement control functions"""
        self.protection = Protection(self)
        self._ipAddr = ipAddress
        self._ontPort = ontPort
        self._tcpPort = None
        self._ecEnabled = True
        self._userName = ''
        self._pwdRequired = False
        self._versionInfo = None
        self._mp = _OntTcpConnection()
        ## an initialized OntRemote object is needed here
        self.cfp2 = Cfp2(ipAddress, self._parsePortString(ontPort)[1], self)
        self.vtm  = VtmConfiguration(ipAddress, ontPort, self)
        ## memorize for reconnect - also update by protection
        self._user = None
        self._pwd  = None

    def connect(self, user=None, password=None):
        """Establish a connection to an ONT measurement port.

        In case of a protected port the user and the password must be provided.
        """
        
        self._user = user
        self._pwd  = password
        
        self._tcpPort, self._userName, self._pwdRequired = self._queryTcpPort(self._ipAddr, self._ontPort)
        if not self._isConnected:
            try:
                self._mp.connect(self._ipAddr, self._tcpPort)
                self._isConnected = True
            except Exception as ex:
                raise OntRemoteError('Connecting to %s, port %s failed: %s' % (self._ipAddr, self._ontPort, ex))
            # Remove errors eventually pending from previous sessions
            self.getErrorsFromErrorQueue()
            try:
                if self._checkProtection(self._userName, self._pwdRequired, user, password):
                    # For older SW version - just to be safe:
                    self.sendScpi('*prompt off')
                else:
                    # if a dedicated login function is provided this exception should be removed.
                    raise OntRemoteError('Connecting to %s, port %s failed - user and password required' % (self._ipAddr, self._ontPort))
            except OntRemoteError as ex:
                try:
                    self.disconnect()
                except:
                    pass
                finally:
                    raise ex
            except Exception as ex:
                try:
                    self.disconnect()
                except:
                    pass
                finally:
                    raise OntRemoteError(ex)
            ## read SW version - used to control access to new APIs
            versionInfo = self.receiveScpi(':DIAG:SW?')
            self._versionInfo = parseVersionInfo(versionInfo)

    def disconnect(self):
        """Disconnect from the ONT measurement port.
        """
        
        self._user = None
        self._pwd  = None
        self._disconnect()

    def sendScpi(self, command):
        """Send an SCPI command that does not cause a response string.

        Note: When error checking is enabled the timeout mechanism described for receiveScpi()
        also applies for the (internal) query of the error queue.
        """
        
        errors = []
        try:
            self._send(command)
        except OntRemoteError as ex:
            errors = ex._hint
        except Exception as ex:
            errors.append(ex)
        finally:
            try:
                if self._ecEnabled:
                    self._scpiErrorCheck() # in case of error, raises OntRemoteError
            except OntRemoteError as ex:
                for msg in ex._hint:
                    errors.append(msg)
            except Exception as ex:
                errors.append(ex)

            if errors:
                raise OntRemoteError(errors)


    def receiveScpi(self, query, timeout=None):
        """Send an SCPI query and wait for the response string.

        When the optional timeout value is omitted the default setting as defined by setTimeout() is used.
        If the waiting time exceeds this timeout value an exception is raised.
        """
        
        response = ''
        errors = []
        try:
            response = self._receive(query, timeout)
        except OntRemoteError as ex:
            errors = ex._hint
        except Exception as ex:
            errors.append(ex)
        finally:
            try:
                if self._ecEnabled:
                    self._scpiErrorCheck() # in case of error, raises OntRemoteError
            except OntRemoteError as ex:
                for msg in ex._hint:
                    errors.append(msg)
            except Exception as ex:
                errors.append(ex)

            if errors:
                raise OntRemoteError(errors)

        return response

    def setErrorCheck(self, errorCheck):
        """Enable/disable automatic error queue checks after sendScpi and receiveScpi calls.
        """
        
        self._ecEnabled = errorCheck

    def getErrorsFromErrorQueue(self):
        """Read all pending error queue entries. 
        
        Returns a list of error messages. If there are no entries in the error queue an empty list is returned.
        """
        
        entries = []
        while True:
            errorCheck = self._receive(':SYST:ERR?')
            errorCheckText = errorCheck.split(',')[1]
            if errorCheckText == '"No error"':
                break;
            entries.append(errorCheck)
        return entries

    def getTimeout(self):
        """Return the current timeout value as integer [seconds].
        """
        
        return self.timeout

    def setTimeout(self, timeout):
        """Set the timeout applied for receiveScpi calls.

        The pre-defined value is 30 seconds.
        """
        
        self.timeout = timeout

    def _send(self, command):
        """Send an SCPI command that does not cause a response string.

        No ONT error logger check.
        """
        
        if command.find('?') >= 0:
            response = self._receive(command)
            raise OntRemoteError("Unhandled response: %s" % (response, ))
        try:
            self._mp.sendScpi(command)
        except OntRemoteError as ex:
            errors = []
            for hint in ex._hint:
                error = 'Sending data to %s, port %s failed: %s' % (self._ipAddr, self._ontPort, hint)
                errors.append(error)
            raise OntRemoteError(errors)
        except Exception as ex:
            raise OntRemoteError('Sending data to %s, port %s failed: %s' % (self._ipAddr, self._ontPort, ex))

    def _receive(self, query, timeout=None):
        """Send an SCPI query and wait for the response string.

        No ONT error logger check.
        """
        
        if query.find('?') < 0:
            raise OntRemoteError("Malformed SCPI query: %s" % (query, ))
        if timeout is None:
            timeout = self.timeout
        try:
            response = self._mp.receiveScpi(query, timeout)
        except OntRemoteError as ex:
            errors = []
            for hint in ex._hint:
                error = 'Receiving data from %s, port %s failed: %s' % (self._ipAddr, self._ontPort, hint)
                errors.append(error)
            raise OntRemoteError(errors)
        except Exception as ex:
            raise OntRemoteError('Receiving data from %s, port %s failed: %s' % (self._ipAddr, self._ontPort, ex))
        return response

    def _queryTcpPort(self, ipAddr, ontPortString):
        tcpPort = None
        userName = ''
        pwdRequired = False
        go_on = False
        admin = _OntTcpConnection(ipAddr, 5001)
        try:
            admin.connect()
        except:    # need specific exception here
            raise OntRemoteError('%s: Unable to connect to administrative port 5001' % (ipAddr, ))

        # For older SW version - just to be safe:
        try:
            admin.sendScpi('*prompt off')
            data = self._queryPortList(admin)
        except OntRemoteError:    # need specific exception here
            raise
        except:
            raise OntRemoteError('%s: Unable to communicate with administrative port 5001' % (ipAddr, ))
        else:
            (tcpPort, userName, pwdRequired) = self._getTcpPort(ipAddr, ontPortString, data)
        finally:
            admin.disconnect()
        return (tcpPort, userName, pwdRequired)

    def _getTcpPort(self, ipAddr, ontPortString, prtmList):
        portDescriptionList = prtmList.split(',')
        searchString = ontPortString
        for portDescription in portDescriptionList:
            if portDescription.find(searchString) == 0:
                ## limit number of items to 4, this enables future versions to add items to portDescription
                portId, tcpPort, userName, protection = portDescription.split(':')[:4]
                pwdRequired = False
                if protection.find('protected') == 0:
                    pwdRequired = True
                return (int(tcpPort), userName, pwdRequired)

        portsAvailable = []
        for portDescription in portDescriptionList:
            ## read required item only, this enables future versions to add items to portDescription
            portId = portDescription.split(':')[0]
            portsAvailable.append(portId)
        availablePorts = ', '.join(portsAvailable)
        raise OntRemoteError('%s: Requested measurement port not found: %s. Ports available: %s' % (ipAddr, ontPortString, availablePorts))

    def _checkProtection(self, userName, pwdRequired, user, password):
        if pwdRequired:
            if (user is None) or (password is None):
                return False
            self.protection._login(user, password)
        return True

    def _scpiErrorCheck(self):
        entries = self.getErrorsFromErrorQueue()
        if entries:
            raise OntRemoteError(entries)

    def _parsePortString(self, ontPort):
        ids = ontPort.split('/')
        if len(ids) != 4:
            raise OntRemoteError("Invalid format of ONT measurement port: '%s' - expected: '/0/SlotNo/PortNo'" % (ontPort, ))
        mainframe = int(ids[1])
        slot = int(ids[2])
        port = int(ids[3])
        return (mainframe, slot, port)
        
    def _queryPortList(self, tcpPort):
        mainframeIDN = tcpPort.receiveScpi('*IDN?', self.timeout)[1:-1]
        itemList = mainframeIDN.split(',')
        numberOfSlots = itemList[1].split('-')[1]
        timeout = 90.0      # 5.0 sec per slot + 30
        try:
            numberOfSlots = int(numberOfSlots)
            timeout = max(60.0 + (numberOfSlots % 100) * 5.0, self.timeout) 
        except ValueError:
            pass
        data = tcpPort.receiveScpi(':PRTM:LIST?', timeout)
        return data
    
    def _disconnect(self):
        if self._isConnected:
            try:
                self._mp.disconnect()
            except Exception as ex:
                raise OntRemoteError('Disconnecting from %s, port %s failed: %s' % (self._ipAddr, self._ontPort, ex))
            finally:
                self._isConnected = False
    
    def _reconnect(self):
        self.connect(self._user, self._pwd)

