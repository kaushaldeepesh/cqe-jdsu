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
from ._error import OntRemoteError

class Application:
    """The application control API. It is used by the OntRemote instance and should not be used on its own.
    """

    def __init__(self, scpiConnection):
        self.timeout = 240
        self._con = scpiConnection

    def loadNew(self):
        """Load the "New-Application".
        """

        res = self._con.receiveScpi(':INST:LOAD "New-Application";*OPC?', self.timeout)

    def load(self, applicationName):
        """Load an application with user defined settings.
        """

        if applicationName.find('"') != 0:
            applicationName = '"' + applicationName + '"'
        scpiQuery =  ':INST:LOAD %s,"public";*OPC?' % (applicationName, )
        res = self._con.receiveScpi(scpiQuery, self.timeout)
        self._con._scpiErrorCheck()
        # Starting the measurement immediately after loading the stack may result in a
        # measurement duration of 1s with no respect to the gating time set.
        # To avoid this, sleep here for 1 s.
        sleep(1)

    def setLayerStack(self, stack, devMode=None, thruMode=None, portConf=None, jitterwander=None):
        """Configure the signal structure.

        Optional arguments: if argument is omitted the current setting is used without modification.
        Any argument!=None is applied and possibly causes an OntRemoteError exception.

        Depending on the measurement HW used only a subset of the listed values is applicable.
        stack:      For a list of supported stacks see `ONT-600_RemoteControl.pdf`
        devMode:    'TERM' | 'THRU' | 'WRAP' | 'DEWRAP'
        thruMode:   This argument is applicable only if devMode == 'THRU'.
                    'PHYS' | 'SONSDH' | 'OTN'
        portConf:   MTM:    'DEEP_ANALYSIS' | 'PORT_LOAD' | 'MIXED_PORT_LOAD'
                    CFP2:   'SINGLE_PORT' | 'DUAL_PORT' | 'ADD_DROP'
                    VTMs:   'VTM_1P' | 'VTM_2P' | 'VTM_4P'
                    Others: 'NOT_APPLICABLE'
        jitterwander: Applicable for Jitter/Wander HW modules only.
                    'JITTER' | 'WANDER' | 'JITTER2' | 'WANDER2'
        """

        defaultTimeout = self._con.timeout
        try:
            self._con.timeout = self.timeout
            res = self._con.receiveScpi(':INST:CAT?')
            # if no application loaded load new-application first.
            if res == '""':
                self.loadNew()
            self._con.sendScpi(':INST:CONF:EDIT:OPEN ON;*WAI')
            moduleType = self._con.receiveScpi(':INST:CONF:MOD:TYPE?')
            if portConf is not None:
                if moduleType == 'MODMTM':
                    portConfList = self._con.receiveScpi(':INST:CONF:EDIT:PORT:CONF:CAT?').split(',')
                    if portConf in portConfList:
                        cmd = ':INST:CONF:EDIT:PORT:CONF %s;*WAI' % portConf
                        self._con.sendScpi(cmd)
                        actualPortConf = self._con.receiveScpi(':INST:CONF:EDIT:PORT:CONF?')
                    else:
                        raise OntRemoteError('Requested Port Configuration not available: %s' % (portConf, ))
                else:
                    currentPortConf = self._con.receiveScpi(':INST:CONF:EDIT:PORT:CONF?')
                    if portConf != currentPortConf:
                        raise OntRemoteError('Port Configuration mismatch: requested=%s / configured=%s' % (portConf, currentPortConf))
            if devMode is not None:
                cmd = ':INST:CONF:EDIT:DEV:MODE %s;*WAI' % devMode
                self._con.sendScpi(cmd)
            cmd = ':INST:CONF:EDIT:LAY:STAC %s' % stack
            self._con.sendScpi(cmd)
            if thruMode is not None:
                cmd = ':INST:CONF:EDIT:THRU:MODE %s;*WAI' % thruMode
                self._con.sendScpi(cmd)
            if jitterwander is not None:
                cmd = ':INST:CONF:EDIT:JWAN:MODE %s;*WAI' % jitterwander
                self._con.sendScpi(cmd)
            res = self._con.receiveScpi(':INST:CONF:EDIT:APPL ON;*OPC?')
            self._con._scpiErrorCheck()
            # Starting the measurement immediately after loading the stack may result in a
            # measurement duration of 1s with no respect to the gating time set.
            # To avoid this, sleep here for 1 s.
            sleep(1)
        finally:
             self._con.timeout = defaultTimeout

    def unload(self):
        """Unload the currently active application independent of its load history (new-application, user application, stack change, save, ...).

        Raises an OntRemoteError if no application is loaded.
        """

        applicationName = self._con.receiveScpi(':INST:CAT?')
        cmd = ':INST:DEL %s;*OPC?' % applicationName
        res = self._con.receiveScpi(cmd, self.timeout)

    def loaded(self):
        """Return the name and attributes of the currently loaded application.

        If no application is loaded an empty dict is returned.
        """

        result = {}
        result['thruMode'] = None
        result['jitterwander'] = None
        applName = self._con.receiveScpi(':INST:CAT?')
        result['name'] = applName[1:-1]
        if not result['name']:
            return {}
        # an application is loaded, query the other parameters
        result['portConf'] = self._con.receiveScpi(':INST:CONF:PORT:CONF?')
        result['devMode'] = self._con.receiveScpi(':INST:CONF:DEV:MODE?')
        if result['devMode'].upper() == 'THRU':
            result['thruMode'] = self._con.receiveScpi(':INST:CONF:THRU:MODE?')
        result['stack'] = self._con.receiveScpi(':INST:CONF:LAY:STAC?')
        jitterAvail = self._con.receiveScpi(':INST:CONF:JWAN:AVAIL?')
        if jitterAvail.upper() != 'OFF':
            result['jitterwander'] = self._con.receiveScpi(':INST:CONF:JWAN:MODE?')
        return result


    ## future starts here
    def save(self, applicationName, results=True, eventLists=True, override=False):
        """Save the current settings as a user application.
        ATTENTION: results=False also disables eventLists!

        If 'applicationName' already exists the current settings are not stored
        and an exception is raised (default behavior).
        With argument 'override' set to True the current settings are always
        saved. If a user application with the same name already exists its
        content will be overriden.
        
        If 'results' is set to False, also event list saving is disabled.
        """

        cmd = ':INST:SAVE:APP'
        if results:
            if eventLists:
                cmd = ':INST:SAVE:RES:HIST'
            else:
                cmd = ':INST:SAVE:RES'
        cmd = cmd + ' "%s";*OPC?'
        cmd = cmd % (applicationName, )
        if not override:
            if applicationName in self.loadable():
                raise OntRemoteError('Save Application cancelled: "%s" already exists' % applicationName)
        res = self._con.receiveScpi(cmd, self.timeout)

    def loadable(self):
        """Return a list reporting the loadable user applications (i.e. previously saved applications).
        """

        applications = self._con.receiveScpi(':INST:LOAD? "public"')
        loadableApplications = []
        if applications != '""':
            applications = applications[1:-1]
            loadableApplications = applications.split(',')
        return loadableApplications

    def availableStacks(self, devMode=None, portConf=None):
        """Return a list reporting the available stacks.

        Optional arguments: if argument is omitted the current setting is used without modification.
        Any argument!=None is applied and possibly causes an OntRemoteError exception.

        Depending on the measurement HW used only a subset of the listed values is applicable.
        devMode:    'TERM' | 'THRU' | 'WRAP' | 'DEWRAP'
        portConf:   MTM:    'DEEP_ANALYSIS' | 'PORT_LOAD' | 'MIXED_PORT_LOAD'
                    CFP2:   'SINGLE_PORT' | 'DUAL_PORT' | 'ADD_DROP'
                    VTMs:   'VTM_1P' | 'VTM_2P' | 'VTM_4P'
                    Others: 'NOT_APPLICABLE'
        """

        availableStacks = None
        portConfRestore = None
        devModeRestore = None
        thruModeRestore = None
        jitterwanderRestore = None
        editOpen = None
        try:
            applicationName = self._con.receiveScpi(':INST:CAT?')
            unloadApplication = False
            if applicationName == '""':
                self.loadNew()
                unloadApplication = True
            editOpen = self._con.receiveScpi(':INST:CONF:EDIT:OPEN?')
            self._con.receiveScpi(':INST:CONF:EDIT:OPEN ON;*OPC?')
            ## store original settings
            portConfRestore = self._con.receiveScpi(':INST:CONF:EDIT:PORT:CONF?')
            devModeRestore = self._con.receiveScpi(':INST:CONF:EDIT:DEV:MODE?')
            if devModeRestore.upper() == 'THRU':
                thruModeRestore = self._con.receiveScpi(':INST:CONF:THRU:MODE?')
            jitterAvail = self._con.receiveScpi(':INST:CONF:JWAN:AVAIL?')
            if jitterAvail.upper() != 'OFF':
                jitterwanderRestore = self._con.receiveScpi(':INST:CONF:JWAN:MODE?')
            if portConf is not None:
                moduleType = self._con.receiveScpi(':INST:CONF:MOD:TYPE?')
                if moduleType == 'MODMTM':
                    portConfList = self._con.receiveScpi(':INST:CONF:EDIT:PORT:CONF:CAT?').split(',')
                    if portConf in portConfList:
                        cmd = ':INST:CONF:EDIT:PORT:CONF %s;*WAI' % portConf
                        self._con.sendScpi(cmd)
                        actualPortConf = self._con.receiveScpi(':INST:CONF:EDIT:PORT:CONF?')
                    else:
                        raise OntRemoteError('Requested Port Configuration not available: %s' % (portConf, ))
                else:
                    currentPortConf = self._con.receiveScpi(':INST:CONF:EDIT:PORT:CONF?')
                    if portConf != currentPortConf:
                        raise OntRemoteError('Port Configuration mismatch: requested=%s / configured=%s' % (portConf, currentPortConf))
            if devMode is not None:
                self._con.receiveScpi(':INST:CONF:EDIT:DEV:MODE %s;*OPC?' % devMode)
            availableStacks = self._con.receiveScpi(':INST:CONF:EDIT:LAY:STAC:CAT?')
        except:
            raise
        finally:
            if editOpen != 'ON':
                ## if application was not in edit mode this will implicitly restore the previous settings
                self._con.receiveScpi(':INST:CONF:EDIT:OPEN OFF;*OPC?')
            else:
                # processing order: restore highest hierarchy first
                if portConfRestore is not None:
                    self._con.receiveScpi(':INST:CONF:EDIT:PORT:CONF %s;*OPC?' % portConfRestore)
                if devModeRestore is not None:
                    self._con.receiveScpi(':INST:CONF:EDIT:DEV:MODE %s;*OPC?' % devModeRestore)
                if thruModeRestore is not None:
                    self._con.receiveScpi(':INST:CONF:EDIT:THRU:MODE %s;*OPC?' % thruModeRestore)
                if jitterwanderRestore is not None:
                    self._con.receiveScpi(':INST:CONF:EDIT:JWAN:MODE %s;*OPC?' % jitterwanderRestore)
            if unloadApplication:
                self.unload()
        if availableStacks is not None:
            availableStacks = availableStacks.split(',')
            if len(availableStacks) == 1 and availableStacks[0].upper() == 'OFF':
                availableStacks = []
        return availableStacks


    def _unloadAll(self):
        """
        Unload the currently active applications independent of their load history (new-application, user application, stack change, save, ...).

        Raises an OntRemoteError if no application is loaded.
        """
        cmd = ':INST:DEL ALL;*OPC?'
        res = self._con.receiveScpi(cmd, self.timeout)
