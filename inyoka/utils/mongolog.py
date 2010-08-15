# -*- coding: utf-8 -*-
"""
    inyoka.utils.mongolog
    ~~~~~~~~~~~~~~~~~~~~~

    Simple logging module that uses a mongodb server to log our
    exceptions.  Maybe this can be advanced some day to create nearly
    real-time statistics about ubuntuusers.de.

    :copyright: 2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import os
import sys
import time
import logging
import traceback

from logging import CRITICAL, ERROR, WARNING, INFO, DEBUG
from socket import gethostname
from datetime import datetime
from hashlib import md5
from threading import Lock

from inyoka import INYOKA_REVISION
from inyoka.conf import settings

try:
    from pymongo.connection import Connection
    from pymongo.errors import AutoReconnect
except ImportError:
    Connection = None


DEFAULT_PRIORITIES = {
    CRITICAL:   'blocker',
    ERROR:      'critical',
    WARNING:    'major',
    INFO:       'minor',
    DEBUG:      'trivial'
}


_connection = None
_connection_lock = Lock()

def get_mdb_database(authenticate=True):
    global _connection
    data = settings.MONGODB_DATA
    if not data['host'] or not data['db']:
        return

    _connection_attempts = 0
    while _connection_attempts < 5:
        try:
            if _connection is None:
                _connection = Connection(data['host'], data['port'])
            database = _connection[data['db']]
            if authenticate and data['user']:
                database.authenticate(data['user'], data['password'])
            break
        except AutoReconnect:
            _connection_attempts += 1
            time.sleep(0.1)
    return database


class SimpleFormatter(logging.Formatter):

    def format(self, record):
        record.message = record.getMessage()
        record.asctime = self.formatTime(record, self.datefmt)
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
        dct = dict(record.__dict__)
        dct['revision'] = INYOKA_REVISION
        return self._fmt % dct


raw_formatter = SimpleFormatter()


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


def get_traceback_frames(exc_info):
    frames = []
    tb = exc_info[2]
    while tb is not None:
        # support for __traceback_hide__ which is used by a few libraries
        # to hide internal frames.
        if tb.tb_frame.f_locals.get('__traceback_hide__'):
            tb = tb.tb_next
            continue
        filename = tb.tb_frame.f_code.co_filename
        function = tb.tb_frame.f_code.co_name
        lineno = tb.tb_lineno - 1
        module_name = tb.tb_frame.f_globals.get('__name__')
        frames.append({
            'filename': filename,
            'function': function,
            'lineno': lineno + 1,
            'vars': tb.tb_frame.f_locals.items(),
            'id': id(tb),
        })
        tb = tb.tb_next

    if not frames:
        frames = [{
            'filename': '<unknown>',
            'function': '?',
            'lineno': '?',
        }]

    return frames


def serialize_as_much_as_possible(frame):
    result = {}
    vars = [(key, [repr(v) for v in value] if '__iter__' in dir(value) else repr(value))
                  for key, value in frame['vars']]

    result['vars'] = vars
    for item in ('filename', 'function', 'lineno', 'id'):
        result[item] = frame[item]

    return result


class MongoHandler(logging.Handler):
    """ Custom log handler

    Logs all messages to a mongo collection. This  handler is
    designed to be used with the standard python logging mechanism.
    """

    def __init__(self, collection='errors', level=logging.NOTSET):
        """ Init log handler and store the collection handle """
        logging.Handler.__init__(self, level)
        if Connection is None:
            # make everything a dummy
            self.emit = lambda r: None
        self.formatter = SimpleFormatter()
        self.collection = collection

    def emit(self, record):
        """ Store the record to the collection. Async insert """
        database = get_mdb_database(True)
        if database is None:
            return
        collection = database[self.collection]


        # check if the hash already exists, if so increment
        # the occured counter.
        record_hash = get_record_hash(record)
        existing = collection.find_one({'hash': record_hash})
        if existing:
            collection.update({'hash': record_hash}, {'$inc': {'occured': +1}})
        else:
            # insert a new entry if the error did not occur yet
            fmt = self.formatter
            record.message = record.getMessage()
            if record.exc_info:
                if not record.exc_text:
                    record.exc_text = fmt.formatException(record.exc_info)
            record.asctime = fmt.formatTime(record, fmt.datefmt)

            frames = get_traceback_frames(record.exc_info)
            msg = {
                'hash': get_record_hash(record),
                'revision': INYOKA_REVISION,
                'created': datetime.utcnow(),
                'status': 'new',
                'levelname': record.levelname,
                'info': get_exception_message(record.exc_info),
                'message': record.message,
                'asctime': record.asctime,
                'exc_text': record.exc_text,
                'occured': 1,
                'frame': serialize_as_much_as_possible(frames[-1]),
            }

            collection.save(msg)
