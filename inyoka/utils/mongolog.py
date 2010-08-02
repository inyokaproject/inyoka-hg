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

    if _connection is None:
        _connection = Connection(data['host'], data['port'])

    database = _connection[data['db']]
    if authenticate and data['user']:
        database.authenticate(data['user'], data['password'])
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
        record.message = record.getMessage()
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatter.formatException(record.exc_info)

        dct = dict(record.__dict__)
        dct['hash'] = get_record_hash(record)
        dct['revision'] = INYOKA_REVISION
        dct['created'] = datetime.utcnow()
        dct['status'] = 'new'

        # drop not neccessary information
        for info in ('exc_info', 'relativeCreated', 'thread'):
            dct.pop(info, None)

        database = get_mdb_database(True)
        if database is None:
            return

        collection = database[self.collection]
        collection.save(dct)
