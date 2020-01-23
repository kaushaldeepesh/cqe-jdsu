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

$Date: 2019-05-13 13:13:52 +0200 (Mo, 13 Mai 2019) $

"""

import calendar
import time

from ._error import OntRemoteError
from .util import OntEventDecoder as _OntEventDecoder
from .util import OntEventDecoderError as _OntEventDecoderError

class Parameter:
    """This class represents a scalar ONT parameter.

    The ONT SCPI types are automatically mapped to the appropriate Python types.
    'Integer' to int(), 'Numeric' to float(), 'Discrete' and 'String' to str().
    """

    def __init__(self, ontRemote, scpiName, opcQuery = False):
        """
        ontRemote:  An instance of OntRemote.OntRemote
        scpiName:   SCPI command name
        opcQuery:   When enabled the setting of a value is followed by a *OPC? query.
        """

        self._name = scpiName.rstrip('?')
        self._con = ontRemote
        self._type = None
        self._storedValue = None
        self._formatString = ' %s'
        self._txCmd = self._con.sendScpi
        if opcQuery:
            self._formatString += ';*OPC?'
            self._txCmd = self._con.receiveScpi

    def set(self, value):
        """The value type depends on the SCPI parameter registered with the object.

        As a short cut it is also possible to assign a value by calling the object directly (e.g. myParameter('ON')).
        """

        if self._type is None:
            tmp = self._configureType()
            self.set(value)
            return
        assert 0, "Parameter.set(): inconsistent internal state."

    def get(self):
        """Return the current value of the parameter.

        The return type depends on the SCPI parameter registered with the object.
        """

        if self._type is None:
            value = self._configureType()
            if isinstance(value, str):
                if value[0] == '"':
                    value = value[1:-1]
                    value = value.replace('""', '"')
            return value
        assert 0, "Parameter.get(): inconsistent internal state."

    def range(self):
        """Return a tuple with (min, max) values of the registered SCPI parameter.

        Available for numeric parameters only.
        """

        cmd = self._name + '?'
        result = self._con.receiveScpi(cmd + ' min;' + cmd + ' max')
        result = result.split(';')
        if result[0].find('.') > -1:
            return float(result[0]), float(result[1])
        return int(result[0]), int(result[1])

    def store(self):
        """Store the current setting internally.
        """

        self._storedValue = self.get()

    def restore(self):
        """Restore the previously stored setting.
        """

        if self._storedValue is None:
            raise OntRemoteError('Parameter.restore(): the member function store() must have been called before.')
        self.set(self._storedValue)

    def type(self):
        """Return the Python type of the registered parameter.

        Note: The SCPI 'Discrete' type has the Python type 'str'.
        """

        if self._type is None:
            self._type = type(self.get())
        return self._type

    def cat(self):
        """Return a list of available discrete values.

        Available for discrete parameters only.
        Note: This function is experimental and not fully tested.
        """

        cmd = self.name + ':CAT?'
        result = self._con.receiveScpi(cmd)
        result = result.split(',')
        if result and not result[0]: result = result[1:]
        return result

    def _configureType(self):
        cmd = self._name + '?'
        value = self._con.receiveScpi(cmd)
        self.set = self._set
        try:
            if value.find('.') > -1:
                value = float(value)
            else:
                value = int(value)
            self.get = self._getNumeric
        except ValueError:
            if value[0] == '"':
                self.set = self._setScpiString
            self.get = self._getString

        self._type = type(value)
        return value

    def _setScpiString(self, value):
        """Set the value of a parameter of SCPI type 'String'.

        The quotation marks required for SCPI strings are automatically added by this function.
        The required duplication of enclosed quotation marks is also taken care of.
        """

        prefix = '"'
        postfix = '"'
        value = value.replace('"', '""')
        cmd = self._name + self._formatString % ( prefix + value + postfix, )
        self._txCmd(cmd)

    def _set(self, value):
        """Set the value of a parameter of SCPI type 'Integer', 'Numeric' or 'Discrete'.
        """

        cmd = self._name + self._formatString % (value, )
        self._txCmd(cmd)

    def _getString(self):
        """Return the current value of the parameter as a Python 'str'.

        This is the SCPI 'Discrete' and 'String' specific get() function.
        The enclosing quotation marks of an SCPI 'String' are removed.
        """

        cmd = self._name + '?'
        value = self._con.receiveScpi(cmd)
        if value[0] == '"':
            value = value[1:-1]
            value = value.replace('""', '"')
        return value

    def _getNumeric(self):
        """Return the current value of the parameter as a Python 'int' or 'float'.

        This is the SCPI 'Integer' and 'Numeric' specific get() function.
        """

        cmd = self._name + '?'
        value = self._con.receiveScpi(cmd)
        if value.find('.') > -1:
            value = float(value)
        else:
            value = int(value)
        return value

    def __call__(self, value):
        """Set the parameter's value.

        The type of value depends on the SCPI parameter registered with the object.
        """

        self.set(value)

    def __getattr__(self, name):
        if name =='name': return self._name
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name =='name': raise AttributeError('The registered parameter must not be changed.')
        self.__dict__[name] = value


class BlockParameter:
    """This class represents an ONT block parameter.

    The ONT SCPI types are automatically mapped to the appropriate Python types.
    'Integer' to int(), 'Numeric' to float(), 'Discrete' and 'String' to str().
    """

    def __init__(self, ontRemote, scpiName, opcQuery = False):
        """
        ontRemote:  An instance of OntRemote.OntRemote
        scpiName:   SCPI command name
        opcQuery:   When enabled the setting of values is followed by a *OPC? query.
        """

        tmpName = scpiName.lower()
        tmpName = tmpName.rstrip('?')
        endPos = tmpName.rfind(':bloc')
        if endPos > 0:
            self._name = scpiName[:endPos]
        else:
            self._name = scpiName[:len(tmpName)]
        self._con = ontRemote
        self._type = None
        self._storedValue = None
        self._postfixString = ''
        self._txCmd = self._con.sendScpi
        if opcQuery:
            self._postfixString = ';*OPC?'
            self._txCmd = self._con.receiveScpi

    def set(self, index, values):
        """index:  Start setting the values at index. The index is zero based.
        values: A list or tuple of values to be set.
        """

        if isinstance(values, str) or isinstance(values, float) or isinstance(values, int):
            # convert a single value into a list of values
            values = list( (values,))
        cmd = self._name + '? %d,%d' % (index, len(values))
        response = self._con.receiveScpi(cmd)
        response = response.split(',')
        self._configureType(response[0])
        self.set(index, values)

    def get(self, index = 0, length = None):
        """index:  Start reading the settings at index. The index is zero based.
        length: Number of settings to read.
        """

        if length == None:
            cmd = self._name + ':BLOC?'
        else:
            cmd = self._name + '? %d,%d' % (index, length)
        response = self._con.receiveScpi(cmd)
        response = response.split(',')
        if (length == None) and index > 0:
            response = response[index:]
            if not response:
                ## force an ONT exception because index >= size
                cmd = self._name + '? %d,%d' % (index, 1)
                response = self._con.receiveScpi(cmd)
        response = self._parseValues(response)
        return response

    def store(self):
        """Store the current settings internally.
        """

        self._storedValue = self.get()

    def restore(self):
        """Restore the previously stored settings.
        """

        if self._storedValue is None:
            raise OntRemoteError('BlockParameter.restore(): the member function store() must have been called before.')
        self.set(0, self._storedValue)

    def type(self):
        """Return the Python type of the registered block parameter's values.

        Note: The SCPI 'Discrete' type has the Python type 'str'.
        """

        if self._type is None:
            # get() sets self._type if unknown
            self.get(0,1)
        return self._type

    def cat(self, index):
        """Return a list of available discrete values.

        Available for discrete block parameters only.
        Note: This function is experimental and not fully tested.
        """

        cmd = self.name + ':CAT? %s' % (index, )
        result = self._con.receiveScpi(cmd)
        result = result.split(',')
        return result

    def _configureType(self, item):
        self.set = self._set
        try:
            if item.find('.') > -1:
                item = float(item)
            else:
                item = int(item)
            self._parseValues = self._parseNumericValues
        except ValueError:
            if item[0] == '"':
                self.set = self._setScpiString
                self._parseValues = self._parseStringValues
            else:
                self._parseValues = self._parseDiscreteValues
        self._type = type(item)

    def _setScpiString(self, index, values):
        """
        index:  Start setting the values at index. The index is zero based.
        values: A list or tuple of values to be set.

        Set the values of a block parameter of SCPI type 'String'.
        The quotation marks required for SCPI strings are automatically added by this function.
        """

        if isinstance(values, str):
            # convert a single string into a list of strings
            values = list( (values,))
        cmd = self._name + ' %d,%d' % (index, len(values))
        for item in values:
            prefix = ''
            if item[0] != '"': prefix = '"'
            postfix = ''
            if item[-1] != '"': postfix = '"'
            cmd += ',%s' % (prefix + item + postfix, )
        cmd += self._postfixString
        self._txCmd(cmd)

    def _set(self, index, values):
        """index:  Start setting the values at index. The index is zero based.
        values: A list or tuple of values to be set.

        Set the values of a block parameter of SCPI type 'Integer', 'Numeric' or 'Discrete'.
        """

        if isinstance(values, str) or isinstance(values, float) or isinstance(values, int):
            # convert a single value into a list of values
            values = list( (values,))
        cmd = self._name + ' %d,%d' % (index, len(values))
        for item in values:
            cmd += ',%s' % (item, )
        cmd += self._postfixString
        self._txCmd(cmd)

    def _parseValues(self, valueList):
        """SCPI 'Discrete' needs no transformation
        """

        item = valueList[0]
        self._configureType(valueList[0])
        valueList = self._parseValues(valueList)
        return valueList

    def _parseDiscreteValues(self, valueList):
        """SCPI 'Discrete' needs no transformation."""
        return valueList

    def _parseStringValues(self, valueList):
        """SCPI 'String': remove enclosing quotation marks.
        """

        resultList = []
        for item in valueList:
            item = item[1:-1]
            resultList.append(item)
        return resultList

    def _parseNumericValues(self, valueList):
        """SCPI 'Numeric' or 'Integer': convert to native Python types.
        """

        if valueList[0].find('.') > -1:
            valueList = list(map(float, valueList)) # list: required for compatibility Python 2/3
        else:
            valueList = list(map(int, valueList))
        return valueList

    def __call__(self, index, value):
        """Set the block parameter's values.

        index:  Start setting the values at index. The index is zero based.
        values: A list or tuple of values to be set.

        The type of value depends on the SCPI parameter registered with the object.
        """

        self.set(index, value)

    def __getattr__(self, name):
        if name == 'name': return self._name
        raise AttributeError(name)

    def __setattr__(self, name, value):
        if name == 'name': raise AttributeError('The registered parameter must not be changed.')
        self.__dict__[name] = value


class ParameterGroup:
    """This class holds an aggregation of parameters and/or block parameters.
    """

    def __init__(self, ontRemote, groupDescription):
        """
        ontRemote:        An instance of OntRemote.OntRemote.
        groupDescription: A group name or text that describes the purpose of this group.
        """

        self._con = ontRemote
        self.description = groupDescription
        self._parameterList = []

    def addParameters(self, parameters):
        """Add parameters and/or block parameters to the group.

        parameters: A list (or tuple) of parameter definitions.
                    Each parameter definition is a tuple with (name, scpiName) or (name, scpiName, opcQuery).
                    The default for opcQuery is False.
                    A block parameter must include :BLOC as final node in the scpiName.
        """

        for item in parameters:
            if len(item) == 2:
                name,scpiName = item
                queryOpc = False;
            elif len(item) == 3:
                name,scpiName,queryOpc = item
            else:
                raise OntRemoteError('ParameterGroup %s:  unexpected parameter list item: item should provide name and scpiName. Optionally *OPC query can be enabled.' % self.description)

            if name in self.__dict__:
                raise OntRemoteError('ParameterGroup %s: Registered name must be unique: %s' % (self.description, name))
            if self._isBlockParameter(scpiName):
                self.__dict__[name] = BlockParameter(self._con, scpiName, queryOpc)
            else:
                self.__dict__[name] = Parameter(self._con, scpiName, queryOpc)
            self._parameterList.append(self.__dict__[name])

    def store(self):
        """Store the current settings internally.
        """

        for param in self._parameterList:
            param.store()

    def restore(self):
        """Restore the previously stored settings.

        The settings are restored in the order the parameters were registered.
        """

        for param in self._parameterList:
            param.restore()

    def _isBlockParameter(self, name):
        name = name.rstrip('?')
        name = name.lower()
        pos = name.rfind(':bloc')
        return (pos > 0) and ((len(name) - pos) == 5)


def _decodeResult(result, scpiName):
    result = result.split(',')
    if len(result) != 2:
        raise OntRemoteError('ScpiResult %s: Unexpected number of return values' % scpiName)
    try:
        valid = (int(result[0]) == 1)
    except ValueError:
        valid = False
        raise OntRemoteError('ScpiResult %s: Problem decoding valid flag' % scpiName)
    if valid:
        try:
            value = result[1]
            if value.find('.') > -1:
                value = float(value)
            else:
                value = int(value)
        except ValueError:
            if value[0] == '"':
                # remove quotation marks of SCPI string result
                value = value[1:-1]
    else:
        value = None
    return valid, value


class Result:
    """This class represents a scalar ONT result.

    The ONT SCPI types are automatically mapped to the appropriate Python types.
    """

    def __init__(self, ontRemote, scpiName):
        """
        ontRemote: An instance of OntRemote.OntRemote.
        scpiName: SCPI command name.
        """

        self.name = scpiName.rstrip('?')
        self._con = ontRemote

    def get(self):
        """Return the current value of the result.

        If the result is invalid the Python None is returned.
        For valid results the value type depends on the ONT result registered with the object.
        """

        cmd = self.name + '?'
        result = self._con.receiveScpi(cmd)
        valid, value = _decodeResult(result, self.name)
        if valid:
            return value
        return None

    def final(self):
        """Return the final value of the result after the measurement was stopped.

        If the result is invalid the Python None is returned.
        For valid results the value type depends on the ONT result registered with the object.
        """

        cmd = ':SENS:DATA:FIN? "%s"' % (self.name,)
        result = self._con.receiveScpi(cmd)
        valid, value = _decodeResult(result, self.name)
        if valid:
            return value
        return None


class BlockResult:
    """This class represents an ONT block result.

    The ONT SCPI types are automatically mapped to the appropriate Python types.
    """

    def __init__(self, ontRemote, scpiName):
        """
        ontRemote: An instance of OntRemote.OntRemote.
        scpiName: SCPI command name.
        """

        tmpName = scpiName.lower()
        tmpName = tmpName.rstrip('?')
        endPos = tmpName.rfind(':bloc')
        if endPos > 0:
            self.name = scpiName[:endPos]
        else:
            self.name = scpiName[:len(tmpName)]
        self._con = ontRemote

    def get(self, index = 0, length = None):
        """Return a list of the current values of the result.

        index:  Start reading the results at index. The index is zero based.
        length: Number of values to report.

        If the result is invalid the Python None is returned.
        """

        if length is None:
            cmd = self.name + ':BLOC?'
        else:
            cmd = self.name + '? %d,%d' % (index, length)
        valid, values = self._readValues(cmd)
        if valid:
            if (length is None) and (index > 0):
                values = values[index:]
                if not values:
                    ## force an ONT exception because index >= LENG
                    cmd = self.name + '? %d,%d' % (index, 1)
                    values = self._con.receiveScpi(cmd)
            return values
        return None

    def length(self):
        """Return the number of currently available results.
        """

        cmd = self.name + ':LENG?'
        result = self._con.receiveScpi(cmd)
        try:
            result = int(result)
        except ValueError:
            raise OntRemoteError('BlockResult %s: Unexpected result: %s' % cmd, result)
        return result

    def final(self, index = 0, length = None):
        """Return a list of the final values of the result after the measurement was stopped.

        index:  Start reading the results at index. The index is zero based.
        length: Number of values to report.

        If the result is invalid the Python None is returned.
        """

        cmd = ':SENS:DATA:FIN? "%s"' % (self.name,)
        valid, values = self._readValues(cmd)
        if valid:
            usedLength = len(values)
            if index > 0:
                values = values[index:]
            if length is not None:
                if length < len(values):
                    values = values[:length]
            if not values:
                ## Current results raise an exception if :LENG > 0 and index > LENG.
                ## Final results have no corresponding API - thus exception must be raised locally
                raise OntRemoteError('BlockResult %s: Index out of boundary - used length is %d' % cmd, usedLength)
            return values
        return None

    def _readValues(self, cmd):
        values = self._con.receiveScpi(cmd)
        values = values.split(',')
        valid = False
        try:
            resultCount = int(values[0])
            valid = (resultCount > -1)
        except ValueError:
            valid = False
            raise OntRemoteError('BlockResult %s: Problem decoding valid flag' % cmd)
        if valid:
            values = values[1:]
            if resultCount != len(values):
                raise OntRemoteError('BlockResult %s: Inconsistent result reported: length: %s / No of items: %s' % cmd, resultCount, len(values))
            # be prepared for a list of length zero
            if values:
                try:
                    if values[0].find('.') > -1:
                        values = list(map(float, values)) # list: required for compatibility Python 2/3
                    else:
                        values = list(map(int, values))
                except ValueError:
                    # Check for SCPI string delimiters and remove them
                    if values[0][0] == '"':
                        resultList = []
                        for item in values:
                            item = item[1:-1]
                            resultList.append(item)
                        values = resultList
        else:
            values = []
        return (valid, values)


class ExtendedBlockResult:
    """This class represents an ONT extended block result.

    The ONT SCPI types are automatically mapped to the appropriate Python types.
    """

    def __init__(self, ontRemote, scpiName):
        """
        ontRemote: An instance of OntRemote.OntRemote.
        scpiName: SCPI command name.
        """

        tmpName = scpiName.lower()
        tmpName = tmpName.rstrip('?')
        endPos = tmpName.rfind(':ebloc')
        if endPos > 0:
            self.name = scpiName[:endPos]
        else:
            self.name = scpiName[:len(tmpName)]
        self._con = ontRemote

    def get(self, index = 0, length = None):
        """Return a list of the current values of the result.

        index:  Start reading the results at index. The index is zero based.
        length: Number of values to report.

        If the result is invalid the Python None is returned.
        For the extended block result also single results may be invalid.
        Thus the list may also include Python None elements.
        For valid results the value type depends on the ONT result registered with the object.
        """

        if length is None:
            cmd = self.name + ':EBLOC?'
        else:
            cmd = self.name + ':ERANG? %d,%d' % (index, length)
        valid, values = self._readValues(cmd)
        if valid:
            if (length is None) and (index > 0):
                values = values[index:]
                if not values:
                    ## force an ONT exception because index >= LENG
                    cmd = self.name + ':ERANG? %d,%d' % (index, 1)
                    values = self._con.receiveScpi(cmd)
            return values
        return None

    def length(self):
        """Return the number of currently available results.
        """

        cmd = self.name + ':LENG?'
        result = self._con.receiveScpi(cmd)
        try:
            result = int(result)
        except ValueError:
            raise OntRemoteError('ExtendedBlockResult %s: Unexpected result: %s' % cmd, result)
        return result

    def final(self, index = 0, length = None):
        """Return a list of the final values of the result after the measurement was stopped.

        index:  Start reading the results at index. The index is zero based.
        length: Number of values to report.

        If the result is invalid the Python None is returned.
        For the extended block result also single results may be invalid.
        Thus the list may also include Python None elements.
        For valid results the value type depends on the ONT result registered with the object.
        """

        cmd = ':SENS:DATA:FIN? "%s"' % (self.name,)
        valid, values = self._readValues(cmd)
        if valid:
            usedLength = len(values)
            if index > 0:
                values = values[index:]
            if length is not None:
                if length < len(values):
                    values = values[:length]
            if not values:
                ## Current results raise an exception if :LENG > 0 and index > LENG.
                ## Final results have no corresponding API - thus exception must be raised locally
                raise OntRemoteError('ExtendedBlockResult %s: Index out of boundary - used length is %d' % cmd, usedLength)
            return values
        return None

    def _readValues(self, cmd):
        values = self._con.receiveScpi(cmd)
        values = values.split(',')
        valid = False
        try:
            resultCount = int(values[0])
            valid = (resultCount > -1)
        except ValueError:
            valid = False
            raise OntRemoteError('ExtendedBlockResult %s: Problem decoding valid flag' % cmd)
        resultValues = []
        if valid:
            values = values[1:]
            if resultCount != int(len(values) / 2):
                raise OntRemoteError('ExtendedBlockResult %s: Inconsistent result reported: length: %s / No of items: %s' % (cmd, resultCount, int(len(values) / 2)))
            # be prepared for a list of length zero
            if values:
                for ii in range(resultCount):
                    flag = values[2*ii]
                    value = values[2*ii + 1]
                    try:
                        flag = (int(flag) == 1)
                    except ValueError:
                        flag = False
                        raise OntRemoteError('ExtendedBlockResult %s: Problem decoding valid flag at index %d' % self.name, ii)
                    if flag:
                        try:
                            if value.find('.') > -1:
                                value = float(value)
                            else:
                                value = int(value)
                        except ValueError:
                            if value[0] == '"':
                                # remove quotation marks of SCPI string result
                                value = value[1:-1]
                    else:
                        value = None
                    resultValues.append(value)
        return (valid, resultValues)


class ResultGroup:
    """This class manages a group of scalar results.

    A single function call returns a dictionary including all registered results.
    """

    def __init__(self, ontRemote, groupDescription):
        """
        ontRemote:        An instance of OntRemote.OntRemote.
        groupDescription: A group name or text that describes the purpose of this group.
        """

        self.description = groupDescription
        self.nameList = []
        self._names = set()
        self._cmd = ''
        self._con = ontRemote

    def addResults(self, resultRoot, results):
        """Register a list of scalar results.

        resultRoot: The resultRoot is a SCPI root name, i.e. the SCPI nodes common to all results of this call of addResults().
                    The ellipsis ... is used to mark the node which will be replaced by the SCPI nodes listed in results.
        results:    The results list provides the SCPI sub-nodes which replace the ellipsis ... of the resultRoot.
                    An item of results may either provide the SCPI node(s) only or a tuple with (name, scpiNodes).
                    If the name is provided it is used as the key into the dictionary.
                    If the name is not provided the SCPI node is used as the key.
        """

        cmd = ''
        for item in results:
            if isinstance(item, str):
                item = (item, item)
            if item[0] in self._names:
                raise OntRemoteError('ResultGroup %s: Result name must be unique: %s' % (self.description, item[0]))
            else:
                self._names.add(item[0])
            item = (item[0], self._scpiCmd(resultRoot, item[1]))
            cmd += item[1]
            cmd += ';'
            self.nameList.append(item)
        if self._cmd:
            self._cmd += ';'
        self._cmd += cmd[:-1]

    def _addBlockResult(self, resultName, index=0, length=None):
        """Not yet implemented."""
        pass

    def _addExtendedBlockResult(self, resultName, index=0, length=None):
        """Not yet implemented."""
        pass

    def get(self):
        """Return a Python dictionary with the names as the dictionary keys.

        Invalid results are set to None.
        The ONT SCPI types are automatically mapped to the appropriate Python types.
        """

        if not self._cmd:
            # raise exception - no results registered
            raise OntRemoteError('ResultGroup %s: No results registered' % (self.description))
        result = self._con.receiveScpi(self._cmd)
        result = result.split(';')
        resDict = {}
        index = 0
        for resultName,scpiName in self.nameList:
            res = _decodeResult(result[index], scpiName)
            if res[0] == 1:
                resDict[resultName] = res[1]
            else:
                resDict[resultName] = None
            index += 1
        return resDict

    def _scpiCmd(self, rootName, scpiName):
        if scpiName[-1] == '?':
            scpiName = scpiName[:-1]
        if scpiName[-1] == ':':
            scpiName = scpiName[:-1]
        if scpiName[0] == ':':
            scpiName = scpiName[1:]
        scpiComponents = self._scpiRootComponents(rootName)
        if len(scpiComponents) == 1:
            cmd = scpiComponents[0] + ':' + scpiName + '?'
        elif len(scpiComponents) == 2:
            cmd = scpiComponents[0] + ':' + scpiName + ':' + scpiComponents[1] + '?'
        # add some sanity checks here
        cmd = cmd.replace('::', ':')
        return cmd

    def _scpiRootComponents(self, rootName):
        if rootName[-1] == '?':
            rootName = rootName[:-1]
        insertMark = ':...'
        scpiComponents = rootName.split(insertMark)
        if len(scpiComponents) == 2 and len(scpiComponents[1]) == 0:
            scpiComponents = scpiComponents[:1]
        if len(scpiComponents) > 2:
            # raise exception because only one wild card marker is supported.
            raise OntRemoteError('ResultGroup %s: Only one wild card position supported, but %d detected: %s' % (self.description, len(scpiComponents), rootName))
        return scpiComponents


class EventList:
    """This class provides access to the ONT event list structure.
    """

    _decodeMinVersion = (37, 0, 2)

    def __init__(self, ontRemote, scpiName, enableDecoding=True):
        """
        ontRemote: An instance of OntRemote.OntRemote.
        scpiName:  SCPI event list name.
        enableDecoding: Enable/disable decoding of the event value.
        """

        self.name = scpiName
        self._con = ontRemote
        self._maxNumberPerCmd = 100
        ## decoder handling
        self._decoder = None
        self._enableDecoding = enableDecoding
        self._decode = self._decodeInit
        ## internal use - no explicit argument
        self._strict = False

    def resetReadPosition(self):
        """Set read 'pointer' to the start position.
        """

        self._con.sendScpi('%s:FIRS' % self.name)

    def entriesToRead(self):
        """Return the number of entries to be read.
        """

        return int(self._con.receiveScpi('%s:NUMB?' % self.name))

    _nsecPerSec = 1000000000
    _nsecPerMsec = 1000000

    def get(self, number, filter=None):
        """Return a list of events.

        number: The number of requested events. The number of events returned may be lower.
                Either because the event list contained fewer events then requested or a filter was applied.
        filter: The filter can be either a single event-ID or a callable object that returns True or False.
                As argument for the callable object a single event dictionary is used.

        For each event the values are stored in a dictionary.
        If a filter is defined only those events are included in the list that match the filter criteria.
        """

        result = []
        availableNo = int(self._con.receiveScpi('%s:NUMB?' % self.name))
        number = min(number, availableNo)
        receivedEvents = 0
        while number > 0:
            perCallCount = min(number, self._maxNumberPerCmd)
            scpiResponse = self._con.receiveScpi('%s? %d' % (self.name, perCallCount))
            res = scpiResponse.split(',')
            if (int(res[0]) != perCallCount):
                raise OntRemoteError('EventList %s: Unexpected number of events - requested: %d / received: %d' % (self.name, perCallCount, int(res[0])))
            if (len(res) != (1 + 25 * perCallCount)):
                raise OntRemoteError('EventList %s: Unexpected event structure - items expected: %d / items received: %d' % (self.name, (1 + 25 * perCallCount), len(res)))

            number -= perCallCount
            receivedEvents += perCallCount
            # convert string result -> Python dictionary
            for ii in range(0, perCallCount*25, 25):
                id = int(res[ii+1])
                startValue = self._getTime(res[ii+2:ii+10])
                stopValue = self._getTime(res[ii+10:ii+18])
                durationValue = (  (int((((((int(res[ii+18]) * 24) + int(res[ii+19])) * 60) + int(res[ii+20])) * 60) + int(res[ii+21])) * EventList._nsecPerSec)
                                 + (int(res[ii+22]) * EventList._nsecPerMsec) + int(res[ii+23]) )
                eventType = int(res[ii+24])
                value = int(res[ii+25])
                event = { 'id': id, 'startTime' : startValue, 'stopTime' : stopValue, 'duration': durationValue, 'type': eventType, 'count' : value }
                event = self._decode(event)
                if filter is None:
                    result.append(event)
                else:
                    if callable(filter):
                        if filter(event):
                            result.append(event)
                    elif id == filter:
                        result.append(event)
        return result

    def next(self):
        """Return a dictionary with event item data.

        If the end of the event list is reached, an empty dictionary is returned.
        """

        result = {}
        count = int(self._con.receiveScpi('%s:NUMB?' % self.name))
        if count > 0:
            scpiResponse = self._con.receiveScpi('%s? 1' % self.name)
            res = scpiResponse.split(',')
            if (len(res) != 26) or (int(res[0]) != 1):
                raise OntRemoteError('EventList %s: Unexpected event structure - data received: %s' % (self.name, res))
            id = int(res[1])
            startValue = self._getTime(res[2:10])
            stopValue = self._getTime(res[10:18])
            durationValue = ( (int((((((int(res[18]) * 24) + int(res[19])) * 60) + int(res[20])) * 60) + int(res[21])) * EventList._nsecPerSec)
                            + (int(res[22]) * EventList._nsecPerMsec) + int(res[23]) )
            eventType = int(res[24])
            value = int(res[25])
            ## debugging - begin
            if False:
                startTime = res[2] + '-' + res[3] + '-' + res[4] + ' ' + res[5] + ':' + res[6] + ':' + res[7] + '.' + res[8]
                stopTime  = res[10] + '-' + res[11] + '-' + res[12] + ' ' + res[13] + ':' + res[14] + ':' + res[15] + '.' + res[16]
                duration  = res[18] + 'd ' + res[19] + 'h ' + res[20] + 'm ' + res[21] + 's ' + res[22] + 'ms'
                # print id, startTime, stopTime, duration, eventType, value
            ## debugging - end
            result = { 'id': id, 'startTime' : startValue, 'stopTime' : stopValue, 'duration': durationValue, 'type': eventType, 'count' : value }
            result = self._decode(result)
        return result

    def skip(self, number):
        """Return the number of actually skipped events.
        """

        if number < 1:
            return number
        noOfEntries = int(self._con.receiveScpi('%s:NUMB?' % self.name))
        number = min(number, noOfEntries)
        skipCount = 0
        while number > 0:
            perCallCount = min(number, self._maxNumberPerCmd)
            ## nobody cares for the result
            self._con.receiveScpi('%s? %d' % (self.name, perCallCount))
            number -= perCallCount
            skipCount += perCallCount
        return skipCount

    def additionalInfo(self):
        """Returns a list of additionalInfo items.

        If the layer does not provide any decoding information, the function returns 'None'.
        If the layer provides decoding information, but events do not include any additional
        information, an empty list is returned.
        Note: The eventID is not reported as additional info.
        """

        self._buildDecoder()
        if self._decoder:
            fieldList = self._decoder.additionalInfo()
            mergedList = []
            for items in fieldList:
                for item in items:
                    if item not in mergedList: mergedList.append(item)
            return mergedList
        return None


    def _getTime(self, dateTime):
        """Convert textual date and time representation into seconds since 01.01.1970

        Note: If the date is less (earlier) than 1970-01-01 a ValueError is raised and the function returns 'None'.
        """

        timeString = dateTime[0] + '-' + dateTime[1] + '-' + dateTime[2] + ' ' + dateTime[3] + ':' + dateTime[4] + ':' + dateTime[5]
        try:
            timeStruct = time.strptime(timeString, '%Y-%m-%d %H:%M:%S')
            timeValue = ( (calendar.timegm(timeStruct) * EventList._nsecPerSec)
                        + (int(dateTime[6]) * EventList._nsecPerMsec) + int(dateTime[7]) )
        except ValueError as e:
            timeValue = None
        return timeValue

    def _decodeInit(self, event):
        """Decoder initialization once.
        """

        self._buildDecoder()
        if self._decoder:
            self._decode = self._decodeEvent
            return self._decodeEvent(event)
        else:
            self._decode = self._decodeEmpty
            return self._decodeEmpty(event)

    def _decodeEvent(self, event):
        """JSON based decoder.
        """

        if event and self._decoder:
            addData = self._decoder.decodeEvent(event['id'])
            event.update(addData)
        return event

    def _decodeEmpty(self, event):
        """NOOP decoder.
        """
        return event

    def _buildDecoder(self, force=False):
        self._decoder = None
        if self._enableDecoding and (self._con._versionInfo >= EventList._decodeMinVersion):
            try:
                formParameter = self._getFormParameter(self._con, self.name)
                if formParameter:
                    formatString = formParameter.get()
                    self._decoder = _OntEventDecoder(formatString, self._strict)
            except _OntEventDecoderError as ex:
                ## Map _OntEventDecoderError to OntRemoteError
                text = '%s' % ex
                raise OntRemoteError(text)

    def _getFormParameter(self, con, eventListName):
        scpiNodes = eventListName.split(':')
        if scpiNodes[-1] in ('SEC', 'MIN', 'HOUR'):
            scpiNodes = scpiNodes[:-1]
        scpiNodes.append('FORM')
        formParaName = ':'.join(scpiNodes)
        queryCmd = '*EXIST? "%s"' % (formParaName, )
        result = int(con.receiveScpi(queryCmd))
        if result:
            return Parameter(con, formParaName)
        return None

