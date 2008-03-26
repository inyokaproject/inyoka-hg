# -*- coding: utf-8 -*-
"""
    inyoka.utils.terminal
    ~~~~~~~~~~~~~~~~~~~~~

    Provides tools for terminals.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import sys


_colors = dict((c, '3%d' % x) for x, c in zip(xrange(8),
    ('black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white')
))
_formats = {
    'bold':         '1',
    'underscore':   '4',
    'blink':        '5',
    'reverse':      '7',
    'conceal':      '8'
}


def get_dimensions():
    """Return the current terminal dimensions."""
    if not hasattr(sys.stdout, 'fileno'):
        return (80, 24)
    from struct import pack, unpack
    from fcntl import ioctl
    from termios import TIOCGWINSZ
    s = pack('HHHH', 0, 0, 0, 0)
    return unpack('HHHH', ioctl(sys.stdout.fileno(), TIOCGWINSZ, s))[1::-1]


class FancyPrinter(object):
    """
    Prints colorful text into a terminal stream.
    """

    def __init__(self, stream=None, color=None, bold=False, underscore=False,
                 blink=False, reverse=False, conceal=False):
        self._stream = stream or sys.stdout
        self._color = color
        self._bold = bold
        self._underscore = underscore
        self._blink = blink
        self._conceal = conceal
        self._reverse = reverse

    def __getattr__(self, attr):
        if attr in _colors:
            attr = ('_color', attr)
        elif attr in _formats:
            attr = ('_' + attr, True)
        elif attr[:2] == 'no' and attr[2:] in _formats:
            attr = ('_' + attr[:2], False)
        else:
            raise AttributeError(attr)
        result = object.__new__(self.__class__)
        result.__dict__.update(self.__dict__)
        setattr(result, *attr)
        return result

    def __call__(self, text):
        if not self._stream.isatty():
            self._stream.write(text)
        else:
            if isinstance(text, unicode):
                encoding = getattr(self._stream, 'encoding') or 'latin1'
                text = text.encode(encoding, 'ignore')
            codes = []
            if self._color is not None:
                codes.append(_colors[self._color])
            for format, val in _formats.iteritems():
                if getattr(self, '_' + format):
                    codes.append(val)
            self._stream.write('\x1b[%sm%s\x1b[0m' % (';'.join(codes), text))
        return self

    __lshift__ = __rlshift__ = __call__
