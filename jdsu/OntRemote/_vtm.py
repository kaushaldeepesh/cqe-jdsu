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

$Date: 2019-05-15 16:01:38 +0200 (Mi, 15 Mai 2019) $

"""
import time
import collections

from ._base import _OntTcpConnection
from ._error import OntRemoteError

class VtmConfiguration:
    """The VTM configuration API. It is used by the OntRemote instance and should not be used on its own.
    """

    _minVersion = (37, 0, 2)

    def __init__(self, ipAddr, portNo, ontRemote):
        self._ipAddr = ipAddr
        self._portNo = portNo
        self._slotNo = int( self._portNo.split('/')[2] )
        self._ontRemote = ontRemote
        self.timeout = 60.0
        self._admin = None

    def configurationStatus(self):
        """Return a list of all VTMs with VTM identifier, configuration, owner and availability.

        VTM identifier: E.g. '/0/3/1'
        configuration:  'VTM_1P' | 'VTM_2P' | 'VTM_4P'
        owner:          The user name. If no user is assigned, None is returned.
        availability:   True if this VTM is available for re-configuration.
        """

        try:
            self._connect()
            partitions = self._partitionStatus()
            scpiQuery = ':BMOD:SLOT%d:VTM:CONF?' % (self._slotNo, )
            result = self._admin.receiveScpi(scpiQuery, self.timeout)
            self._checkErrorLog()
        finally:
            self._disconnect()

        vtmList = result.split(',')
        statusList = []
        for item in vtmList:
            id, vtmType = item.split(':')[:2]
            status = (id, vtmType, partitions[id][0], partitions[id][1])
            statusList.append(status)
        return statusList

    def availableConfigurations(self):
        """Return a list of the VTM configurations available.
        """

        # The list of setable VTM sizes only depends on module capabilities,
        # loaded applications and port protections. Current VTM configuration isn't considered.
        # In other words, the command returns a list of possible VTM sizes accepting a re-configuration.
        scpiQuery = ':BMOD:SLOT%d:VTM:CONF:CAT? %s' % (self._slotNo, self._portNo)
        result = self._processQuery(scpiQuery, 'availableConfigurations()', self.timeout)
        vtmTypes = []
        vtmTypeList = result.split(',')
        if vtmTypeList and not vtmTypeList[0]: vtmTypeList = vtmTypeList[1:]
        for item in vtmTypeList:
            vtmType = item.split(':')[1]
            vtmTypes.append(vtmType)
        return vtmTypes

    def getConfiguration(self):
        """Return the current VTM configuration.
        """

        try:
            self._connect()
            scpiQuery = ':BMOD:SLOT%d:VTM:CONF? %s' % (self._slotNo, self._portNo)
            result = self._admin.receiveScpi(scpiQuery, self.timeout)
            self._checkErrorLog()
            size = result.split(':')[1]
        finally:
            self._disconnect()
        return size

    def setConfiguration(self, vtmConfig):
        """Set the VTM configuration.

        VTM configurations: 'VTM_1P' | 'VTM_2P' | 'VTM_4P'

        Note: The VTM configuration can only be changed if no applications are loaded on any of the affected VTMs.
        """

        wasConnected = self._ontRemote._isConnected
        self._ontRemote._disconnect()
        try:
            scpiQuery = ':BMOD:SLOT%d:VTM:CONF %s:%s;*OPC?' % (self._slotNo, self._portNo, vtmConfig)
            result = self._processQuery(scpiQuery, 'setConfiguration():', self.timeout)
            time.sleep(0.5)
        except:
            raise
        finally:
            ## connect again (-> user and password is handled internally)
            if wasConnected:
                self._ontRemote._reconnect()

    def _partitionStatus(self, doConnect = False):
        """Return the status of all partitions.
        """

        try:
            if doConnect: self._connect()
            scpiQuery = ':BMOD:SLOT%d:VTM:PART:STAT?' % (self._slotNo, )
            result = self._admin.receiveScpi(scpiQuery, self.timeout)
            self._checkErrorLog()
        finally:
            if doConnect: self._disconnect()
        partitions = collections.OrderedDict()
        partitionList = result.split(',')
        for part in partitionList:
            partId, username, usage = part.split(':')[:3]
            if username == '': username = None
            free = bool(usage.lower() == 'unused')
            partitions[partId] = (username, free)
        return partitions

    def _processQuery(self, scpiQuery, errorLabel = '', timeout = 30.0):
        admin = _OntTcpConnection(self._ipAddr, 5001)
        try:
            admin.connect()
        except:    # need specific exception here
            raise OntRemoteError('%s: Unable to connect to administrative port 5001' % (self._ipAddr, ))

        errorCheck = admin.receiveScpi(':SYST:ERR?')
        errorCheckText = errorCheck.split(',')[1]
        errorCheckText = errorCheckText.lower()
        if '"no error"' not in errorCheckText:
            raise OntRemoteError("Administration Port %s: %s" % (self._ontRemote._ipAddr, errorCheck,))

        self._login(admin)
        # For older SW version - just to be safe:
        try:
            admin.sendScpi('*prompt off')
            data = admin.receiveScpi(scpiQuery, timeout)
        except:    # need specific exception here
            raise OntRemoteError('%s: Unable to communicate with administrative port 5001' % (self._ipAddr, ))
        else:
            errlog = admin.receiveScpi(':SYST:ERR?', timeout)
            errorCheckText = errlog.split(',')[1]
            errorCheckText = errorCheckText.lower()
            if '"no error"' in errorCheckText:
                pass
            else:
                # toDo: ONT errorlogger: with or without additional info from script?
                # raise OntRemoteError('%s/slot %d: %s %s' % (self._ipAddr, self._slotNo, errorLabel, errlog))
                raise OntRemoteError('%s' % (errlog, ))
        finally:
            admin.disconnect()
        return data

    def _login(self, admin):
        if self._ontRemote._pwd is not None:
            cmd = ':BMOD:SLOT%d:USER:REG "%s","%s"' % (self._slotNo, self._ontRemote._user, self._ontRemote._pwd)
            try:
                admin.sendScpi(cmd)
            except:
                raise
            opcResult = int(admin.receiveScpi('*OPC?'))
            ## toDo: check OPC result
            errorCheck = admin.receiveScpi(':SYST:ERR?')
            errorCheckText = errorCheck.split(',')[1]
            errorCheckText = errorCheckText.lower()
            if '"no error"' not in errorCheckText:
                raise OntRemoteError("Login to %s: %s" % (admin._ipAddr, errorCheck,))


    def _versionCheck(self):
        if self._ontRemote._versionInfo is None:
            raise OntRemoteError('%s:%s: Version unknown - connection to VTM required' % (self._ipAddr, self._portNo))
        else:
            if self._ontRemote._versionInfo < VtmConfiguration._minVersion:
                reqVersion = '%d.%d.%d' % ( VtmConfiguration._minVersion[0], VtmConfiguration._minVersion[1], VtmConfiguration._minVersion[2] )
                actVersion = '%d.%d.%d' % ( self._ontRemote._versionInfo[0], self._ontRemote._versionInfo[1], self._ontRemote._versionInfo[2] )
                raise OntRemoteError('%s:%s: Version required: %s  version used: %s' % (self._ipAddr, self._portNo, reqVersion, actVersion))


    def _connect(self):
        self._admin = _OntTcpConnection(self._ipAddr, 5001)
        try:
            self._admin.connect()
        except:    # need specific exception here
            raise OntRemoteError('%s: Unable to connect to administrative port 5001' % (self._ipAddr, ))

        try:
            self._checkErrorLog()
            self._admin.sendScpi('*prompt off')
        except:    # need specific exception here
            raise OntRemoteError('%s: Unable to communicate with administrative port 5001' % (self._ipAddr, ))

    def _disconnect(self):
        self._admin.disconnect()
        self._admin = None

    def _checkErrorLog(self):
        errorCheck = self._admin.receiveScpi(':SYST:ERR?')
        errorCheckText = errorCheck.split(',')[1]
        errorCheckText = errorCheckText.lower()
        if '"no error"' not in errorCheckText:
            raise OntRemoteError("Administration Port %s: %s" % (self._ontRemote._ipAddr, errorCheck,))
