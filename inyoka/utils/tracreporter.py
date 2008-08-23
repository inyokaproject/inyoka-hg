# -*- coding: utf-8 -*-
"""
    inyoka.utils.tracreporter
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    This module implements a log handler that reports into a trac.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import urllib2
import csv
import re
import traceback
from Cookie import SimpleCookie
from threading import Thread
from inyoka.conf import settings
from inyoka.utils.urls import url_encode
from inyoka import INYOKA_REVISION

try:
    from hashlib import md5
except ImportError:
    from md5 import new as md5
from logging import Handler, Formatter, CRITICAL, ERROR, WARNING, \
     INFO, DEBUG


ts_input_re = re.compile(r'<input(.*?name="ts".*?)/?>')
value_re = re.compile(r'value="(.*?)"')

USER_AGENT = 'Trac logging handler/0.1'
DEFAULT_PRIORITIES = {
    CRITICAL:   'blocker',
    ERROR:      'critical',
    WARNING:    'major',
    INFO:       'minor',
    DEBUG:      'trivial'
}


class SimpleFormatter(Formatter):

    def format(self, record):
        record.message = record.getMessage()
        record.asctime = self.formatTime(record, self.datefmt)
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        dct = dict(record.__dict__)
        dct['revision'] = INYOKA_REVISION
        return self._fmt % dct


raw_formatter = Formatter()
description_formatter = SimpleFormatter("""\
%(message)s

=== Context ===
|| '''Level''' || %(levelname)s ||
|| '''First occurrence''' || %(asctime)s ||
|| '''Module''' || %(module)s ||
|| '''Line''' || %(lineno)s ||
|| '''Revision''' || %(revision)s ||""")

comment_formatter = SimpleFormatter("""\
'''New occourrence''' on %(asctime)s in `%(module)s:%(lineno)s`\
 (revision: %(revision)s)""")

summary_formatter = SimpleFormatter('%(message)s at %(module)s:%(lineno)s (r%(revision)s)')

def get_record_hash(record):
    # if the record is a traceback, hash the traceback only
    if record.exc_info:
        lines = traceback.format_exception(*record.exc_info)
        message = ''.join(lines)
    # otherwise hash the message
    else:
        message = raw_formatter.format(record)
    if isinstance(message, unicode):
        message = message.encode('utf-8', 'replace')
    return md5(message).hexdigest()


def get_exception_message(exc_info):
    if exc_info and exc_info[0] is not None:
        return traceback.format_exception_only(*exc_info[:2])[0].strip()


class TracHandler(Handler):
    """
    A handler that reports tickets to the trac.  The url to the trac should
    be the URL to the trac root, not to the newticket page.  If the trac
    requires authentication use the (nonstandard) username:password syntax
    in the HTTP URL.  The logging happens in a separate thread so that the
    app doesn't lock up on error reporting.
    """

    def __init__(self):
        Handler.__init__(self)
        self.trac = Trac()

    def emit(self, record):
        Thread(target=self.submit, args=(record,)).start()

    def analyseForTicket(self, record):
        for level, priority in self.trac.priorities:
            if level >= record.levelno:
                break
        else:
            priority = ''
        summary = record.levelname + ':'
        description = description_formatter.format(record)
        exception_message = get_exception_message(record.exc_info)
        if exception_message:
            summary += ' ' + exception_message
            description += '\n\n=== Traceback ===\n\n{{{\n%s\n}}}' % \
                           record.exc_text
        else:
            words = (record.getMessage()).split()
            words.reverse()
            while words and len(summary) < 140:
                summary += ' ' + words.pop()
            if words:
                summary += '...'

        return {
            'summary':      summary,
            'description':  description,
            'priority':     priority,
            'component':    '-',
            'ticket_type':  'servererror',
        }

    def analyseForComment(self, record):
        return {
            'comment':      comment_formatter.format(record)
        }

    def submit(self, record):
        keyword = 'tb_' + get_record_hash(record)
        try:
            record_ticket = self.trac.get_ticket_id(keyword)
            if record_ticket is None:
                details = self.analyseForTicket(record)
                self.trac.submit_new_ticket(keyword, **details)
            else:
                details = self.analyseForComment(record)
                self.trac.submit_comment(record_ticket, **details)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class Trac(object):
    """
    Provides a simple interface to the trac specified in the configuration.
    """

    def __init__(self, trac_url=None, username=None, password=None,
                 priorities=DEFAULT_PRIORITIES, auth_handler=None,
                 ticket_type='defect', charset='utf-8'):
        trac_url = trac_url or settings.TRAC_URL
        if not trac_url.endswith('/'):
            trac_url += '/'
        self.trac_url = trac_url
        self.username = username or settings.TRAC_USERNAME
        self.priorities = priorities.items()
        self.priorities.sort()
        self.trac_charset = charset
        self.ticket_type = ticket_type
        self._cookie = None
        password = password or settings.TRAC_PASSWORD
        if auth_handler is None and password:
            mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
            mgr.add_password(None, self.trac_url, self.username, password)
            auth_handler = urllib2.HTTPBasicAuthHandler(mgr)
        self.opener = urllib2.build_opener(auth_handler)
        self.opener.addheaders = [('User-Agent', USER_AGENT)]

    def get_trac_cookie(self):
        if self._cookie is not None:
            return self._cookie
        request = urllib2.Request(self.trac_url + 'newticket')
        result = self.opener.open(request)
        cookie = SimpleCookie(result.info().get('set-cookie', ''))
        session = cookie.get('trac_session')
        token = cookie.get('trac_form_token')
        self._cookie = cookie
        return cookie

    def open_trac(self, resource, data={}, method='POST', inject_token=True):
        for key, value in data.iteritems():
            if isinstance(value, unicode):
                value = value.encode(self.trac_charset)
                data[key] = value
        cookie = self.get_trac_cookie()
        if inject_token:
            form_token = cookie['trac_form_token']
            if form_token and form_token.value:
                data['__FORM_TOKEN'] = form_token.value
        data = url_encode(data)
        url = self.trac_url + resource
        if method == 'GET':
            if data:
                url += '?' + data
            data = None
        request = urllib2.Request(url, data)
        request.add_header('Cookie', '; '.join(['%s=%s' % (n, m.value)
                                                for n, m in cookie.items()]))
        return self.opener.open(request)

    def get_ticket_id(self, keyword):
        for line in csv.reader(self.open_trac('query', {
                'keywords': '~' + keyword,
                'order_by': 'id',
                'desc':     '1',
                'format':   'csv',
                'resolution': ['!seemstowork', '!fixed', '!worksforme'],
            }, 'GET', False).read().splitlines()):
            if line and line[0].isdigit():
                return int(line[0])

    def submit_new_ticket(self, keywords='', summary='', description='',
                          priority='major', ticket_type=None, component=None,
                          reporter='', milestone=''):
        if not isinstance(keywords, basestring):
            keywords = ' '.join(keywords)
        data = {
            'field_summary':        summary,
            'field_description':    description,
            'field_keywords':       keywords,
            'field_priority':       priority,
            'field_type':           ticket_type or self.ticket_type,
            'field_status':         'new',
            'field_reporter':       reporter,
            'field_milestone':      milestone,
            'author':               self.username,
        }
        if component is not None:
            data['field_component'] = component
        self.open_trac('newticket', data)

    def submit_comment(self, ticket_id, comment=''):
        resource = 'ticket/%d' % ticket_id
        fd = self.open_trac(resource, method='GET')
        ts_input = None
        while ts_input is None:
            line = fd.readline()
            if not line:
                continue
            ts_input = ts_input_re.search(line)
        if ts_input is None:
            return

        old_ts = value_re.search(ts_input.group(1))
        if old_ts is None:
            return
        old_ts = old_ts.group(1)

        self.open_trac(resource, {
            'comment':  comment,
            'action':   'leave',
            'author':   self.username,
            'ts':       old_ts
        })


class TBLoggerHandler(Handler):
    def __init__(self):
        Handler.__init__(self)
        auth_handler = None
        if settings.TRAC_PASSWORD:
            mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
            mgr.add_password(None, 'http://dev.tux21b.org/tb/', settings.TRAC_USERNAME,
                settings.TRAC_PASSWORD)
            auth_handler = urllib2.HTTPBasicAuthHandler(mgr)
        self.opener = urllib2.build_opener(auth_handler)
        self.opener.addheaders = [('User-Agent', USER_AGENT)]

    def emit(self, record):
        Thread(target=self.submit, args=(record,)).start()

    def submit(self, record):
        return
        data = self.analyseForTicket(record)
        data = url_encode(data)
        request = urllib2.Request('http://dev.tux21b.org/tb/new/', data)
        self.opener.open(request).read()

    def analyseForTicket(self, record):
        return {
            'title':        '%s: %s' % (record.levelname, get_exception_message(record.exc_info)),
            'summary':      summary_formatter.format(record),
            'traceback':    record.exc_text,
        }
