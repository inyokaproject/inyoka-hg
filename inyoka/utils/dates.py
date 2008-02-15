# -*- coding: utf-8 -*-
"""
    inyoka.utils.dates
    ~~~~~~~~~~~~~~~~~~

    Various utilities for datetime handling.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import re
import pytz
from datetime import date, datetime, timedelta
from django.utils.dateformat import DateFormat
from django.conf import settings
from inyoka.middlewares.registry import r


MONTHS = ['Januar', 'Februar', u'MÃ¤rz', 'April', 'Mai', 'Juni',
          'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']
WEEKDAYS = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag',
            'Samstag', 'Sonntag']
TIMEZONES = pytz.common_timezones


_iso8601_re = re.compile(
    # date
    r'(\d{4})(?:-?(\d{2})(?:-?(\d{2}))?)?'
    # time
    r'(?:T(\d{2}):(\d{2})(?::(\d{2}(?:\.\d+)?))?(Z?|[+-]\d{2}:\d{2})?)?$'
)


def get_user_timezone():
    """
    Return the timezone of the current user or UTC if there is no user
    available (eg: no web request).
    """
    user = getattr(r.request, 'user', None)
    try:
        return pytz.timezone(user.settings.get('timezone', ''))
    except (AttributeError, LookupError):
        return pytz.UTC


def datetime_to_timezone(dt, enforce_utc=False):
    """
    Convert a datetime object to the user's timezone or UTC if the
    user is not available or `enforce_utc` was set to `True` to enforce
    UTC.
    """
    if enforce_utc:
        tz = pytz.UTC
    else:
        tz = get_user_timezone()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.UTC)
    return dt.astimezone(tz)


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


def format_timedelta(d, now=None, use_since=False, enforce_utc=False):
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
        now = datetime.utcnow().replace(tzinfo=pytz.UTC)
    if type(d) is date:
        d = datetime(d.year, d.month, d.day)
    if now.tzinfo != d.tzinfo:
        d = d.astimezone(now.tzinfo)
    delta = now - d

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


def natural_date(value, prefix=False, enforce_utc=False):
    """
    Format a value using dateformat but also use today, tomorrow and
    yesterday.
    """
    if not isinstance(value, datetime):
        value = datetime(value.year, value.month, value.day)
    if value.tzinfo is not None:
        value = value.astimezone(pytz.UTC)
    delta = value.replace(tzinfo=None) - datetime.utcnow()
    if delta.days == 0:
        return u'heute'
    elif delta.days == -1:
        return u'gestern'
    elif delta.days == 1:
        return u'morgen'
    value = datetime_to_timezone(value, enforce_utc)
    return (prefix and 'am ' or '') + DateFormat(value).format('j. F Y')


def format_time(value, enforce_utc=False):
    """Format a datetime object for time."""
    value = datetime_to_timezone(value, enforce_utc)
    rv = DateFormat(value).format('H:i')
    if enforce_utc:
        rv += ' (UTC)'
    return rv


def format_datetime(value, enforce_utc=False):
    """Just format a datetime object."""
    value = datetime_to_timezone(value, enforce_utc)
    rv = DateFormat(value).format('j. F Y H:i')
    if enforce_utc:
        rv += ' (UTC)'
    return rv


def format_date(value, enforce_utc=False):
    """Just format a datetime object."""
    if isinstance(value, date):
        value = datetime(value.year, value.month, value.day)
    value = datetime_to_timezone(value, enforce_utc)
    rv = DateFormat(value).format('j. F Y')
    if enforce_utc:
        rv += ' (UTC)'
    return rv


def format_specific_datetime(value, alt=False, enforce_utc=False):
    """
    Use German grammar to format a datetime object for a
    specific datetime.
    """
    if value.tzinfo is not None:
        value = value.astimezone(pytz.UTC)
    s_value = value.replace(tzinfo=None)
    delta = s_value - datetime.utcnow()
    if delta.days == 0:
        string = alt and 'heute um ' or 'von heute '
    elif delta.days == -1:
        string = alt and 'gestern um ' or 'von gestern '
    elif delta.days == 1:
        string = alt and 'morgen um ' or 'von morgen '
    else:
        string = (alt and 'am %s um ' or 'vom %s um ') % \
            DateFormat(value).format('j. F Y')
    return string + format_time(value, enforce_utc)


def date_time_to_datetime(d, t):
    """Merge two datetime.date and datetime.time objects into one datetime"""
    return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second,
                    t.microsecond)
