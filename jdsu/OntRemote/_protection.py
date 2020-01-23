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

class Protection:
    """The protection specific functions are provided by this API.
    It is used by the OntRemote instance and should not be used on its own.
    """

    def __init__(self, scpiConnection):
        self._con = scpiConnection
        self._waitTime = 5.0

    def activate(self, user, password):
        """Activate protection.
        
        user:     A non-empty string setting a user name.
        password: A non-empty string defining the password.        
        """
        
        if not user or not password:
            raise OntRemoteError("User and password are mandatory arguments - empty strings not permitted")
        userCmd = ':PRT:USER "%s"' % (user,)
        self._con.sendScpi(userCmd)
        self._con._user = user
        if password is not None:
            pwdCmd = ':PRT:PSWD "%s"' % (password,)
            self._con.sendScpi(pwdCmd)
            self._login(user, password)
            self._con._pwd = password

    def clear(self):
        """Clear password and user protection.
        """
        
        prot, username = self.status()
        if prot:
            ## This command causes an ONT error logger if pwd is already cleared.
            self._con.sendScpi(':PRT:PSWD ""')
        if username:
            ## This command causes an ONT error logger if user name is already cleared.
            self._con.sendScpi(':PRT:USER ""')
        self._con._user = None
        self._con._pwd  = None

    def status(self):
        """Return a tuple with (protection status, user name).
        
        The protection status reports True if a protection is active.
        If no user name is defined, None is returned as user name.
        """
        
        ## a comma is not permitted as part of the user name thus split is safe.
        statusStr, userStr = self._con.receiveScpi(':PRT:PROT?').split(',')
        userStr = userStr[1:-1]
        if not userStr: userStr = None
        return (bool(int(statusStr)), userStr)

    def _login(self, user, password):
        """Login to a protected measurement port.

        A measurement port is protected if a user and a password is defined.
        """
        
        cmd = ':PRT:REG "%s","%s"' % (user, password)
        currentEcState = self._con._ecEnabled;
        self._con._ecEnabled = False
        try:
            self._con.sendScpi(cmd)
        except:
            raise
        finally:
            self._con._ecEnabled = currentEcState
        # We cannot use *opc? in order to wait until user-registration is finished
        # because in case of wrong data, and therefore an unsuccessful login
        # the device prohibits the usage of *opc?. The only chance is to sleep.
        sleep(self._waitTime)
        errorCheck = self._con._receive(':SYST:ERR?')
        errorCheckText = errorCheck.split(',')[1]
        if errorCheckText != '"No error"':
            raise OntRemoteError("Login to %s, port %s failed: %s" % (self._con._ipAddr, self._con._ontPort, errorCheck,))


