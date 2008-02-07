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
from datetime import date, datetime, timedelta
from django.conf import settings
from django.utils.dateformat import DateFormat
from django.utils.tzinfo import LocalTimezone

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

_iso8601_re = re.compile(
    # date
    r'(\d{4})(?:-?(\d{2})(?:-?(\d{2}))?)?'
    # time
    r'(?:T(\d{2}):(\d{2})(?::(\d{2}(?:\.\d+)?))?(Z?|[+-]\d{2}:\d{2})?)?$'
)


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
    return hg_node
INYOKA_REVISION = _get_inyoka_revision()
del _get_inyoka_revision


def interact(offset=0):
    """
    Start a python debugger in the caller frame. If inyoka is in debug
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


def parse_iso8601(value):
    """
    Parse an iso8601 date into a datetime object.
    The timezone is normalized to UTC, we always use UTC objects
    internally.
    """
    m = _iso8601_re.match(value)
    if m is None:
        raise ValueError('not a valid iso8601 date value')

    groups = m.groups()
    args = []
    for group in groups[:-2]:
        if group is not None:
            group = int(group)
        args.append(group)
    seconds = groups[-2]
    if seconds is not None:
        if '.' in seconds:
            args.extend(map(int, seconds.split('.')))
        else:
            args.append(int(seconds))

    rv = datetime(*args)
    tz = groups[-1]
    if tz and tz != 'Z':
        args = map(int, tz[1:].split(':'))
        delta = timedelta(hours=args[0], minutes=args[1])
        if tz[0] == '+':
            rv += delta
        else:
            rv -= delta

    return rv


def format_iso8601(obj):
    """Format a datetime object for iso8601"""
    return obj.strftime('%Y-%d-%mT%H:%M:%SZ')


def format_timedelta(d, now=None, use_since=False):
    """
    Format a timedelta.  Currently this method only works with
    dates in the past.
    """
    chunks = (
        (60 * 60 * 24 * 365, ('m', 'Jahr', 'Jahren')),
        (60 * 60 * 24 * 30, ('m', 'Monat', 'Monaten')),
        (60 * 60 * 24 * 7, ('f', 'Woche', 'Wochen')),
        (60 * 60 * 24, ('m', 'Tag', 'Tagen')),
        (60 * 60, ('f', 'Stunde', 'Stunden')),
        (60, ('f', 'Minute', 'Minuten')),
        (1, ('f', 'Sekunde', 'Sekunden'))
    )
    if now is None:
        now = datetime.now()
    if d.__class__ is date:
        d = datetime(d.year, d.month, d.day)
    if d.tzinfo:
        tz = LocalTimezone(d)
    else:
        tz = None
    delta = now.replace(tzinfo=tz) - d

    since = delta.days * 24 * 60 * 60 + delta.seconds
    if since <= 0:
        return 'gerade eben'

    for idx, (seconds, detail) in enumerate(chunks):
        count = since // seconds
        if count != 0:
            result = [(count, detail)]
            break
    if idx + 1 < len(chunks):
        seconds2, detail = chunks[idx + 1]
        count = (since - (seconds * count)) // seconds2
        if count != 0:
            result.append((count, detail))

    def format(num, genus, singular, plural):
        if not 0 < num <= 12:
            return '%d %s' % (num, plural)
        elif num == 1:
            return {
                'm':        'einem',
                'f':        'einer'
            }[genus] + ' ' + singular
        return ('zwei', 'drei', 'vier', u'fünf', 'sechs',
                'sieben', 'acht', 'neun', 'zehn', 'elf',
                u'zwölf')[num - 2] + ' ' + plural

    return (use_since and 'seit' or 'vor') + ' ' + \
           u' und '.join(format(a, *b) for a, b in result)


def natural_date(value, prefix=False):
    """Format a value using dateformat but also use today, tomorrow and yesterday."""
    if isinstance(value, datetime):
        value = date(value.year, value.month, value.day)
    delta = value - date.today()
    if delta.days == 0:
        return u'heute'
    elif delta.days == -1:
        return u'gestern'
    elif delta.days == 1:
        return u'morgen'
    return (prefix and 'am ' or '') + DateFormat(value).format(settings.DATE_FORMAT)


def format_time(value):
    """Format a datetime object for time."""
    return DateFormat(value).format(settings.TIME_FORMAT)


def format_datetime(value):
    """Just format a datetime object."""
    return DateFormat(value).format(settings.DATETIME_FORMAT)


def format_date(value):
    """Just format a datetime object."""
    if isinstance(value, date):
        value = datetime(value.year, value.month, value.day)
    return DateFormat(value).format(settings.DATE_FORMAT)


def format_specific_datetime(value, alt=False):
    """
    Use German grammar to format a datetime object for a
    specific datetime.
    """
    s_value = date(value.year, value.month, value.day)
    delta = s_value - date.today()
    if delta.days == 0:
        string = alt and 'heute um ' or 'von heute '
    elif delta.days == -1:
        string = alt and 'gestern um ' or 'von gestern '
    elif delta.days == 1:
        string = alt and 'morgen um ' or 'von morgen '
    else:
        string = (alt and 'am %s um ' or 'vom %s um ') % \
            DateFormat(value).format(settings.DATE_FORMAT)
    return string + format_time(value)

def date_time_to_datetime(d, t):
    """Merge two datetime.date and datetime.time objects into one datetime"""
    return datetime(d.year, d.month, d.day,
                    t.hour, t.minute, t.second, t.microsecond)

class deferred(object):
    """
    Deferred properties. Calculated once and then it replaces the
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
