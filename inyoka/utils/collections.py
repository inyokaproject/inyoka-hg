# -*- coding: utf-8 -*-
"""
    inyoka.utils.collections
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Datastructures for collection objects.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""


def _unpickle_multimap(d):
    """
    Helper that creates a multipmap after pickling.  We need this
    because the default pickle system for dicts requires a mutable
    interface which `MultiMap` is not.  Do not make this a closure
    as this object must be pickleable itself.
    """
    m = dict.__new__(MultiMap)
    dict.__init__(m, d)
    return m


class MultiMap(dict):
    """
    A special structure used to represent metadata and other
    data that has multiple values for one key.
    """
    __slots__ = ()

    def __init__(self, sequence):
        for key, value in sequence:
            dict.setdefault(self, key, []).append(value)

    def _immutable(self, *args):
        raise TypeError('%r instances are immutable' %
                        self.__class__.__name__)

    setlist = setdefault = setlistdefault = update = pop = popitem = \
    poplist = popitemlist = __setitem__ = __delitem__ = _immutable
    del _immutable

    def __getitem__(self, key):
        """Get all values for a key."""
        return dict.get(self, key, [])

    def get(self, key, default=None):
        """Return the first value if the requested data doesn't exist"""
        try:
            return self[key][0]
        except IndexError:
            return default

    def __reduce__(self):
        return (_unpickle_multimap, (dict(self),))

    def __repr__(self):
        tmp = []
        for key, values in self.iteritems():
            for value in values:
                tmp.append((key, value))
        return '%s(%r)' % (self.__class__.__name__, tmp)


def flatten_iterator(iter):
    """Flatten an iterator to one without any sub-elements"""
    for item in iter:
        if hasattr(item, '__iter__'):
            for sub in flatten_iterator(item):
                yield sub
        else:
            yield item


class BidiMap(dict):
    """
    A simpler API for simple Bidirectional Mappings.

    Example Usage::

        >>> map = BidiMap({1: 'dumb', 2: 'smartly', 3: 'clever'})
        >>> map[1]
        'dumb'
        >>> map['dumb']
        1

    :param items: A :class:`dict` like object where keys are integers.
    """

    def __init__(self, items=None):
        items = items or {}
        dict.__init__(self, **items)
        self.reversed = dict((v, k) for k, v in self.iteritems())
        if len(self) != len(self.reversed):
            raise ValueError('Values are not unique')

    def __getitem__(self, key):
        """
        Implement object[item] access to this class.
        """
        if isinstance(key, (int, long)):
            return dict.__getitem__(self, key)
        else:
            return self.reversed[key]

    def __repr__(self):
        return 'BidiMap(%s)' % dict.__repr__(self)
