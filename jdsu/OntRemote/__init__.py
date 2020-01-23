# -*- coding: utf-8 -*-
"""
OntRemote package initialization.

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

__version__ = "3.0.0"

try:
    from .build_info import *
    __build__ = __buildInfo__('')
    del __buildInfo__
except:
    __build__ = 'HEAD'


__all__ = ['OntRemote',
           'OntRemoteError',
           'Scpi',
            '__version__',
            '__build__'
           ]

from ._core import OntRemote
from ._error import OntRemoteError
from . import Scpi

