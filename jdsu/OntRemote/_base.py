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

import telnetlib
from time import sleep

from ._error import OntRemoteError


class _OntTcpConnection:
    """This class is intended for internal use only. It may be modified without prior notice.

    Maintains a connection to a remote unit over TCP/IP. The TCP port number selects the ONT measurement port.
    """
    
    _eoc = '\n'
    _eoc_encoded = _eoc.encode('ascii')
    _cr  = '\r'
    
    def __init__(self, ipAddr=None, tcpPort=None):
        self._isConnected = False
        self._ipAddr = ipAddr
        self._tcpPort = tcpPort
        self._errorCheck = False
        self._ts = telnetlib.Telnet()

    def connect(self, ipAddr=None, tcpPort=None):
        """Establish the connection.
        """

        if ipAddr != None:
            self._ipAddr = ipAddr
        if tcpPort != None:
            self._tcpPort = tcpPort
        if not self._isConnected:
            self._ts.open(self._ipAddr, self._tcpPort, 10)
            self._isConnected = True

    def disconnect(self):
        """Terminate the current connection.
        """

        if self._isConnected:
            try:
                self._ts.close()
            except:
                raise
            finally:
                self._isConnected = False

    def sendScpi(self, scpiCmd):
        """Send an SCPI command to the remote unit (no response expected).
        """

        if not self._isConnected:
            raise OntRemoteError('No connection to ONT')

        self._ts.write( scpiCmd.encode('ascii') + self._eoc_encoded)

    def receiveScpi(self, scpiQuery, timeout=5):
        """Send an SCPI query to the remote unit and wait for the response string.
        """

        if not self._isConnected:
            raise OntRemoteError('No connection to ONT')
        # In case of errors while executing the query, ONT remote control aborts the execution
        # of the command and does not execute a *opc? at the end of the query, thus not delivering
        # the '1' to notify us about the end of the command execution. That on the other hand
        # sends us in waiting for the timeout whenever an error occurs.
        # Due to this, we split the *OPC? from the command and send it as a separate command
        # message.
        result = ''
        queryParts = self._splitQuery(scpiQuery)
        for queryPart in queryParts:
            self._ts.write(queryPart.encode('ascii') + self._eoc_encoded)

            if queryPart.find('?') >= 0: # It is a real query, read the result
                queryPartResult = self._ts.read_until(self._eoc_encoded, timeout)
                queryPartResult = queryPartResult.decode('ascii')

                if (not queryPartResult) or (queryPartResult[-1] != self._eoc):
                    raise OntRemoteError('Timeout while waiting for SCPI query response: %s (t:%.1fs)' % (queryPart, timeout))
                # remove eoc and optional <CR> control characters
                if queryPartResult and (queryPartResult[-1] == self._eoc):
                    queryPartResult = queryPartResult[:-1]
                if queryPartResult and (queryPartResult[-1] == self._cr):
                    queryPartResult = queryPartResult[:-1]
                if result:
                    result += ';'
                result += queryPartResult

        return str(result)

    def _splitQuery(self, scpiQuery):
        """
        Split the query using *opc? with no respect to how it is written
        and deliver the parts. Both upper and lower case and whitespace are preserved.
        """
        retval = []
        nonOpcItems = ''
        queryParts = scpiQuery.split(';')
        for item in queryParts:
            if item.upper().find('*OPC?') >= 0:
                if nonOpcItems:
                    retval.append(nonOpcItems)
                    nonOpcItems = ''
                retval.append(item)
            else:
                if nonOpcItems:
                    nonOpcItems = ';'.join((nonOpcItems, item))
                else:
                    nonOpcItems = item
        if nonOpcItems:
            retval.append(nonOpcItems)
        return retval

