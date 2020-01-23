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

$Date: 2019-04-29 14:47:30 +0200 (Mo, 29 Apr 2019) $

"""

from ._base import _OntTcpConnection
from ._error import OntRemoteError

class Cfp2:
    """
    The 40/100G-CFP2 module specific functions are provided by this API.
    It is used by the OntRemote instance and should not be used on its own.

    Note: The mnemonics used here are the same as the CFP2 portConf arguments described for the function 'setLayerStack'.
          The SCPI mnemonics for the 'BMOD:SLOTn:PGRP:MODE' commands additionally have a '_MODE' postfix.
    """

    def __init__(self, ipAddr, slotNo, ontRemote):
        self._ipAddr = ipAddr
        self._slotNo = int(slotNo)
        self._postfix = '_MODE'
        self._ontRemote = ontRemote

    def availableBoardModes(self):
        """
        Return a list of the available board modes.
        """
        scpiQuery = ':BMOD:SLOT%d:PGRP:MODE:CAT? PGRP1' % (self._slotNo, )
        result = self._processQuery(scpiQuery, 'availableBoardModes()', self._ontRemote.timeout)
        boardModes = []
        modeList = result.split(',')
        # remove '_MODE'
        for mode in modeList:
            offset = mode.find(self._postfix)
            boardModes.append(mode[:offset])
        return boardModes

    def getBoardMode(self):
        """
        Return the currently configured board mode.
        """
        scpiQuery = ':BMOD:SLOT%d:PGRP:MODE? PGRP1' % (self._slotNo, )
        result = self._processQuery(scpiQuery, 'getBoardMode():', self._ontRemote.timeout)
        # remove '_MODE'
        offset = result.find(self._postfix)
        return result[:offset]

    def setBoardMode(self, boardMode):
        """
        Set the CFP2 board mode.

        boardMode: 'SINGLE_PORT' | 'DUAL_PORT' | 'ADD_DROP'

        Note: The board mode can only be changed when no application is loaded on the module.
        """
        # append '_MODE'
        boardMode += self._postfix
        scpiQuery = ':BMOD:SLOT%d:PGRP:MODE PGRP1,%s;*OPC?' % (self._slotNo, boardMode)
        result = self._processQuery(scpiQuery, 'setBoardMode():', self._ontRemote.timeout)

    def numberOfPorts(self):
        """
        Return the number of ports supported by this module.

        Note: When called for a module which is not a CFP2 module '0' is returned.
        """
        idnString = self._ontRemote.receiveScpi('*idn?')
        moduleName = idnString.split(',')[1]
        modName = moduleName.upper()
        result = 0
        if 'CFP2' in modName:
            if 'DATA D' in modName or 'PHYD D' in modName:
                result = 2
            elif 'PHY S' in modName or 'PHYD S' in modName or 'DATA S' in modName:
                result = 1
            else:
                raise OntRemoteError('Unexpected CFP2 module type: %s' % (moduleName, ))
        return result

    def _processQuery(self, scpiQuery, errorLabel = '', timeout = 30.0):
        admin = _OntTcpConnection(self._ipAddr, 5001)
        try:
            admin.connect()
        except:    # need specific exception here
            raise OntRemoteError('%s: Unable to connect to administrative port 5001' % (self._ipAddr, ))

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

