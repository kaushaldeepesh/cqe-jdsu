# -*- coding: utf-8 -*-

def __buildInfo__(suffix):
    __rev__ = 110
    __rev_date__ = '2019-05-15 16:01:38'
    __build__ = '%04d' % (__rev__, ) + ', Date: ' + __rev_date__ + suffix
    return __build__

__all__ = [ '__buildInfo__',
          ]
