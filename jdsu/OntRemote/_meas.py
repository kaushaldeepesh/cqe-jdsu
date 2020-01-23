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

$Date: 2019-03-14 16:25:44 +0100 (Do, 14 Mrz 2019) $

"""


import time
from ._error import OntRemoteError

class Measurement:
    """
    The measurement control API. It is used by the OntRemote instance and should not be used on its own.
    """

    def __init__(self, scpiConnection):
        self._con = scpiConnection
        self._sweTime = None

    def isRunning(self):
        """
        Return 'True' if the measurement is running.
        """
        resStr = self._con.receiveScpi(':STAT:OPER:COND?')
        status = int(resStr)
        result = (status & 16) > 0
        return result

    def start(self, gatingTime=None):
        """
        Start a measurement.

        gatingTime: This argument is optional. If not specified the current gatingTime is applied.
                    If set to -1 a continuous measurement is started.
        """
        startCmd = ':INIT:IMM:ALL;*OPC?'
        if gatingTime is None:
            scpiCmd = startCmd
        else:
            scpiCmd = self._sweTimeScpi(gatingTime) + ';' + startCmd
        resStr = self._con.receiveScpi(scpiCmd)

    def stop(self):
        """
        Stop a running measurement.
        """
        self._con.sendScpi(':ABOR')
        doWait = True
        maxWait = 60
        while doWait and maxWait > 0:
            time.sleep(0.5)
            maxWait -= 1
            doWait = self.isRunning()
        if maxWait == 0:
            raise OntRemoteError('Timeout while waiting for measurement stop.')

    def getGatingTime(self):
        """
        Return the configured gatingTime as integer.
        """
        resStr = self._con.receiveScpi(':SENS:SWE:TIME?')
        gatingTime = int(resStr)
        return gatingTime

    def setGatingTime(self, gatingTime):
        """
        Configure the gatingTime.

        If set to -1 a continuous measurement is configured.
        """
        scpiCmd = self._sweTimeScpi(gatingTime)
        self._con.receiveScpi(scpiCmd)

    def _restart(self):
        """
        Stop a running measurement and immediately start it again.
        """
        self._con.receiveScpi(':ABOR;*WAI;:INIT:IMM:ALL;*OPC?')
        
    def _sweTimeScpi(self, gatingTime):
        if gatingTime == -1:
            return ':SENS:SWE:TIME MAX;*OPC?'
        elif gatingTime > 0:
            return ':SENS:SWE:TIME %d;*OPC?' % (gatingTime, )
        else:
            raise OntRemoteError('Invalid gatingTime: %d' % (gatingTime, ))

    ## future enhancement ?
    def _storeGatingTime(self):
        self._sweTime = self._con.receiveScpi(':SENS:SWE:TIME?')

    def _restoreGatingTime(self):
        if self._sweTime != None:
            self._con.sendScpi(':SENS:SWE:TIME %s' % self._sweTime)

