# -*- coding: utf-8 -*-
"""
    inyoka.utils
    ~~~~~~~~~~~~

    Various application independent utilities.

    :copyright: Copyright 2007 by Armin Ronacher, Benjamin Wiegand,
                Christopher Grebs.
    :license: GNU GPL.
"""
from __future__ import division
import os
import re
import random
import unicodedata
from django.conf import settings


_strip_re = re.compile(r'<!--.*?-->|<[^>]*>(?s)')
_slugify_replacement_table = {
    u'\xdf': 'ss',
    u'\xe4': 'ae',
    u'\xe6': 'ae',
    u'\xf0': 'dh',
    u'\xf6': 'oe',
    u'\xfc': 'ue',
    u'\xfe': 'th'
}
_punctuation_re = re.compile(r'[\s!"#$%&\'()*\-/<=>?@\[\\\]^_`{|}]+')
_username_re = re.compile(r'[\w0-9_]{1,30}(?u)')
_str_num_re = re.compile(r'(?:[^\d]*(\d+)[^\d]*)+')


def _get_inyoka_revision():
    """Get the inyoka version."""
    import inyoka
    from subprocess import Popen, PIPE
    hg = Popen(['hg', 'tip'], stdout=PIPE, stderr=PIPE, stdin=PIPE,
               cwd=os.path.dirname(inyoka.__file__))
    hg.stdin.close()
    hg.stderr.close()
    rv = hg.stdout.read()
    hg.stdout.close()
    hg.wait()
    hg_node = None
    if hg.wait() == 0:
        for line in rv.splitlines():
            p = line.split(':', 1)
            if len(p) == 2 and p[0].lower().strip() == 'changeset':
                hg_node = p[1].strip()
                break
    return hg_node.split(':')[0]
INYOKA_REVISION = _get_inyoka_revision()
del _get_inyoka_revision


def interact(offset=0):
    """
    Start a python debugger in the caller frame.  If inyoka is in debug
    mode this function is available globally as ``INTERACT()``.
    """
    import pdb, sys
    frm = sys._getframe(offset + 1)
    p = pdb.Pdb()
    p.prompt = '>>> '
    p.reset()
    p.interaction(frm, None)


def increment_string(s):
    """Increment a number in a string or add a number."""
    m = _str_num_re.search(s)
    if m:
        next = str(int(m.group(1))+1)
        start, end = m.span(1)
        return s[:max(end - len(next), start)] + next + s[end:]
    return s + '2'


def color_fade(c1, c2, percent):
    """Fades two html colors"""
    new_color = []
    for i in xrange(3):
        part1 = int(c1[i * 2:i * 2 + 2], 16)
        part2 = int(c2[i * 2:i * 2 + 2], 16)
        diff = part1 - part2
        new = int(part2 + diff * percent / 100)
        new_color.append(hex(new)[2:])

    return ''.join(new_color)


def get_random_password():
    """This function returns a pronounceable word."""
    consonants = 'bcdfghjklmnprstvwz'
    vowels = 'aeiou'
    numbers = '0123456789'
    all = consonants + vowels + numbers
    length = random.randrange(8, 12)
    password = u''.join(
        random.choice(consonants) +
        random.choice(vowels) +
        random.choice(all) for x in xrange(length // 3)
    )[:length]
    return password


def import_string(string):
    """Import a import string."""
    if '.' not in string:
        return __import__(string, None, None)
    module, attr = string.rsplit('.', 1)
    return getattr(__import__(module, None, None, [attr]), attr)


def striptags(string):
    """Remove HTML tags from a string."""
    return u' '.join(_strip_re.sub('', string).split())


def is_valid_username(name):
    return bool(_username_re.search(name))


def slugify(string):
    """Slugify a string."""
    result = []
    for word in _punctuation_re.split(string.strip().lower()):
        if word:
            for search, replace in _slugify_replacement_table.iteritems():
                word = word.replace(search, replace)
            word = unicodedata.normalize('NFKD', word)
            result.append(word.encode('ascii', 'ignore'))
    return u'-'.join(result)


def human_number(number, genus=None):
    """Numbers from 1 - 12 are words."""
    if not 0 < number <= 12:
        return number
    if number == 1:
        return {
            'masculine':    'ein',
            'feminine':     'eine',
            'neuter':       'ein'
        }.get(genus, 'eins')
    return ('zwei', 'drei', 'vier', u'fünf', 'sechs',
            'sieben', 'acht', 'neun', 'zehn', 'elf', u'zwölf')[number - 2]


class deferred(object):
    """
    Deferred properties.  Calculated once and then it replaces the
    property object.
    """

    def __init__(self, func, name=None):
        self.func = func
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = func.__doc__

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = self.func(obj)
        setattr(obj, self.__name__, value)
        return value

    @staticmethod
    def clear(obj):
        """Clear all deferred objects on that class."""
        for key, value in obj.__class__.__dict__.iteritems():
            if getattr(value, '__class__', None) is deferred:
                try:
                    delattr(obj, key)
                except AttributeError:
                    continue
