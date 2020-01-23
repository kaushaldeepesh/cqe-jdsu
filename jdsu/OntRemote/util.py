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

import collections
import json



def parseVersionInfo(versionInfo):
    """Parse the ONT version info string (:DIAG:SW) and return a tuple.

    The build number is experimentally included for fine-grained tests during development.
    """

    if versionInfo[0] == '"':
        versionInfo = versionInfo[1:-1]
    version = versionInfo.split('-')[-2]
    build = versionInfo.split('-')[-1]
    ## this removes any non-digit characters at any position (possibly to forgiving)
    buildNo = int( ''.join([ch for ch in build if ch.isdigit()]) )
    major, minor, bugFix = version.split('.')[:3]
    return (int(major), int(minor), int(bugFix), buildNo)


# string constants - json input tags
TAG_MFEVENTID  = 'MFEVENTID'
TAG_FORMATS  = 'FORMATS'
TAG_FORMAT  = 'FORMAT'
TAG_FORMATID  = 'FORMATID'
TAG_FORMATID_VALUE = 'formatId'
TAG_ENUMS  = 'ENUMS'
TAG_mask  = 'mask'
TAG_shift = 'shift'
TAG_name  = 'name'
TAG_type  = 'type'

## output tags
TAG_eventID = 'eventID'
TAG_additionalInfo = 'additionalInfo'

class OntEventDecoderError(Exception):
    """Base class for exceptions in this module."""


class OntEventDecoder:
    def __init__(self, evtFormatString, strict = False):
        self._strict = strict
        self._formatDict = json.loads(evtFormatString)
        try:
            self._fidShift, self._fidMask = self._buildFormatIdDecoder()
            self._decoderDict, self._tagDict = self._buildDecoderDicts()
        except OntEventDecoderError as ex:
            ## unconditionally raise an exception because mandatory decoding information is broken
            raise ex
        self._enumDict = {}
        if TAG_ENUMS in self._formatDict:
            self._enumDict = self._buildEnumDict()
        if self._strict:
            self._validate()

    def __bool__(self):
        return bool(self._formatDict)

    def decodeEvent(self, value):
        try:
            fmtIndex, values = self._decode(value)
        except OntEventDecoderError:
            if self._strict: raise
            else: return {}
        tags = self._tagDict[fmtIndex]
        result = {}
        addInfoDict = collections.OrderedDict()
        for tag, value in zip(tags, values):
            if tag[0] == TAG_eventID:
                result[tag[0]] = (value, self._interpretedValue(value, tag[1]))
            else:
                addInfoDict[tag[0]] = (value, self._interpretedValue(value, tag[1]))
        if addInfoDict:
            result[TAG_additionalInfo] = addInfoDict
        return result

    def additionalInfo(self):
        """Return items defined as additional info.
        """

        result = []
        for format in self._formatDict[TAG_MFEVENTID][TAG_FORMATS]:
            item = []
            for section in format[TAG_FORMAT]:
                tagname = str(section[TAG_name])
                if tagname != TAG_eventID:
                    item.append(tagname)
            if len(item) > 0:
                result.append(tuple(item))
        return result

    def prettyPrint(self, dumpEnums = False):
        """Public API or specialized function that lists possible enum strings only?
        """

        print("Format-ID Decoder:   Shift = %d    Mask = %X" % (self._fidShift, self._fidMask))
        print("Format-ID    Name       Type     Shift     Mask")
        for format in self._formatDict[TAG_MFEVENTID][TAG_FORMATS]:
            isFirst = True
            fid = format[TAG_FORMATID_VALUE]
            sections = format[TAG_FORMAT]
            for section in sections:
                text = '%6s' % ' '
                if isFirst:
                    text = '%6d' % fid
                    isFirst = False
                text += '   %10s  %6s        %3d   %6X' % (section[TAG_name], section[TAG_type], section[TAG_shift], section[TAG_mask])
                print(text)

        if dumpEnums:
            for typeTag in sorted(self._enumDict.keys()):
                transDict = self._enumDict[typeTag]
                print("Type: %s" % (typeTag,))
                for value in sorted(transDict.keys()):
                    print("  %5d    %s" % (value, transDict[value]))

    def _decode(self, value):
        formatIndex = (value >> self._fidShift) & self._fidMask
        try:
            decoderList = self._decoderDict[formatIndex]
        except KeyError as ex:
            raise OntEventDecoderError('Unexpected format id: %d' % (ex.args[0],))
        resultList = []
        for shiftValue, mask in decoderList:
            resultList.append((value >> shiftValue) & mask)
        return formatIndex, resultList

    def _decodeVerbose(self, value):
        """Obsolet function?
        """

        fmtIndex, values = self._decode(value)
        tags = self._tagDict[fmtIndex]
        results = []
        for tag, value in zip(tags, values):
            results.append('%s: %d (%s)' % (tag[0], value, self._interpretedValue(value, tag[1])))
        results.append('(Format: %d)' % fmtIndex)
        return '  '.join(results)

    def _interpretedValue(self, value, typeTag):
        res = ''
        try:
            res = self._enumDict[typeTag][value]
        except KeyError:
            pass
        return res

    def _buildFormatIdDecoder(self):
        """Returns (shift, mask) tuple needed for decoding the format ID."""
        try:
            fidMask = self._formatDict[TAG_MFEVENTID][TAG_FORMATID][TAG_mask]
            fidShift = self._formatDict[TAG_MFEVENTID][TAG_FORMATID][TAG_shift]
        except KeyError as ex:
            raise OntEventDecoderError('Format ID Decoder: Mandatory tag not found: %s' % (ex, ))
        return fidShift, fidMask

    def _buildDecoderDicts(self):
        """Returns a dict of (shiftValue, mask) pairs for decoding of event result.

        The first index is the format index.
        The second index is the bitfield index. The bitfield order is highest bits first (left to right).
        The second dict returned provides (name, typeTag) tuples in the same order as the decode dict.
        """

        formatDecoder = {}
        formatTags = {}
        try:
            for format in self._formatDict[TAG_MFEVENTID][TAG_FORMATS]:
                fid = format[TAG_FORMATID_VALUE]
                ## for decoding however the natural order is 'left to right'
                ## sections = sorted(format[TAG_FORMAT], key=lambda section: section[TAG_shift], reverse=True)
                bitfieldDecoder = []
                bitFieldTags = []
                sections = format[TAG_FORMAT]
                for section in sections:
                    bitfieldDecoder.append((section[TAG_shift], section[TAG_mask]))
                    bitFieldTags.append((str(section[TAG_name]), str(section[TAG_type])))
                formatDecoder[fid] = bitfieldDecoder
                formatTags[fid] = bitFieldTags
        except KeyError as ex:
            raise OntEventDecoderError('Field Decoder: Mandatory tag not found: %s' % (ex, ))
        return formatDecoder, formatTags

    def _buildEnumDict(self):
        enums = self._formatDict[TAG_ENUMS]
        enumDict = {}
        for typeTag in enums.keys():
            decoder = {}
            for text, value in enums[typeTag].items():
                decoder[value] = str(text)
            enumDict[str(typeTag)] = decoder
        return enumDict

    def _validate(self):
        """
        if not empty dictionary:
            Top level tags:             mandatory: MFEVENTID            -> implicitly checked by _build-functions that rely on tags
                                        optional: ENUMS
            MFEVENTID sub level tags:   mandatory: FORMATID, FORMATS    -> implicitly checked by _build-functions that rely on tags
            FORMATID sub level:         mandatory: shift, mask          -> implicitly checked by _build-functions that rely on tags
            FORMATS sub level:          mandatory: formatId, FORMAT     -> implicitly checked by _build-functions that rely on tags
            FORMAT sub level:           mandatory: name, shift, mask, type  (check also ordering of shift values within FORMAT list)
            Mandatory Format sub level: name== 'eventID' -> case sensitive!!
        """
        if self._formatDict:
            ### check mandatory name 'eventID' for every formatId - should be first in list of fields (logical order)
            for format in self._formatDict[TAG_MFEVENTID][TAG_FORMATS]:
                sections = format[TAG_FORMAT]
                eventIdTag = sections[0][TAG_name]
                if eventIdTag != 'eventID':
                    raise OntEventDecoderError("Validation: Mandatory field 'eventID' expected but found: %s" % (eventIdTag, ))

            ### check for enum references
            enumTypeSet = set()
            for format in self._formatDict[TAG_MFEVENTID][TAG_FORMATS]:
                bitfieldDecoder = []
                bitFieldTags = []
                sections = format[TAG_FORMAT]
                for section in sections:
                    if section[TAG_type] != 'NUM':
                        enumTypeSet.add(section[TAG_type])
            for enumType in enumTypeSet:
                if enumType not in self._enumDict:
                    raise OntEventDecoderError("Validation: Enum type not found: %s" % (enumType, ))


