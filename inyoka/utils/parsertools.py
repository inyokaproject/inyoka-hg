# -*- coding: utf-8 -*-
"""
    inyoka.utils.parsertools
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Useful classes for parsers.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import sys
from operator import itemgetter


class Token(tuple):
    """
    Represents one token.
    """
    __slots__ = ()

    def __new__(self, type, value):
        return tuple.__new__(self, (intern(str(type)), value))

    type = property(itemgetter(0))
    value = property(itemgetter(1))

    def __repr__(self):
        return 'Token(%r, %r)' % (
            self.type,
            self.value
        )


class TokenStreamIterator(object):
    """
    The iterator for tokenstreams.  Iterate over the stream
    until the eof token is reached.
    """

    def __init__(self, stream):
        self._stream = stream

    def __iter__(self):
        return self

    def next(self):
        token = self._stream.current
        if token.type == 'eof':
            raise StopIteration()
        self._stream.next()
        return token


class TokenStream(object):
    """
    A token stream wraps a generator and supports pushing tokens back.
    It also provides some functions to expect tokens and similar stuff.

    Important note: Do never push more than one token back to the
                    stream.  Although the stream object won't stop you
                    from doing so, the behavior is undefined.  Multiple
                    pushed tokens are only used internally!
    """

    def __init__(self, generator):
        self._next = generator.next
        self._pushed = []
        self.current = Token('initial', '')
        self.next()

    @classmethod
    def from_tuple_iter(cls, tupleiter):
        return cls(Token(*a) for a in tupleiter)

    def __iter__(self):
        return TokenStreamIterator(self)

    @property
    def eof(self):
        """Are we at the end of the tokenstream?"""
        return not bool(self._pushed) and self.current.type == 'eof'

    def debug(self, stream=None):
        """Displays the tokenized code on the stream provided or stdout."""
        if stream is None:
            stream = sys.stdout
        for token in self:
            stream.write(repr(token) + '\n')

    def look(self):
        """See what's the next token."""
        if self._pushed:
            return self._pushed[-1]
        old_token = self.current
        self.next()
        new_token = self.current
        self.current = old_token
        self.push(new_token)
        return new_token

    def push(self, token, current=False):
        """Push a token back to the stream (only one!)."""
        self._pushed.append(token)
        if current:
            self.next()

    def skip(self, n):
        """Got n tokens ahead."""
        for x in xrange(n):
            self.next()

    def next(self):
        """Go one token ahead."""
        if self._pushed:
            self.current = self._pushed.pop()
        else:
            try:
                self.current = self._next()
            except StopIteration:
                if self.current.type != 'eof':
                    self.current = Token('eof', None)

    def expect(self, type, value=None):
        """expect a given token."""
        assert self.current.type == type
        if value is not None:
            assert self.current.value == value or \
                   (value.__class__ is tuple and
                    self.current.value in value)
        try:
            return self.current
        finally:
            self.next()

    def test(self, type, value=Ellipsis):
        """Test the current token."""
        return self.current.type == type and \
               (value is Ellipsis or self.current.value == value or
                value.__class__ is tuple and \
                self.current.value in value)

    def shift(self, token):
        """
        Push one token into the stream.
        """
        old_current = self.current
        self.next()
        self.push(self.current)
        self.push(old_current)
        self.push(token)
        self.next()


# from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/107747,
# with some modifications

class OrderedDict(dict):

    def __init__(self, __dct__=None, **items):
        if __dct__:
            dict.__init__(self, __dct__)
        else:
            dict.__init__(self, **items)
        self._keys = dict.keys(self)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        self._keys.remove(key)

    def __setitem__(self, key, item):
        dict.__setitem__(self, key, item)
        if key not in self._keys: self._keys.append(key)

    def clear(self):
        dict.clear(self)
        self._keys = []

    def copy(self):
        dct = self.__class__(self)
        dct._keys = self._keys[:]
        return dct

    def items(self):
        return zip(self._keys, self.values())

    def keys(self):
        return self._keys

    def popitem(self):
        try:
            key = self._keys[-1]
        except IndexError:
            raise KeyError('dictionary is empty')

        val = self[key]
        del self[key]

        return (key, val)

    def setdefault(self, key, failobj = None):
        ret = dict.setdefault(self, key, failobj)
        if key not in self._keys: self._keys.append(key)
        return ret

    def update(self, dct):
        dict.update(self, dct)
        for key in dct.keys():
            if key not in self._keys: self._keys.append(key)

    def values(self):
        return map(self.get, self._keys)
