# -*- coding: utf-8 -*-
"""
    inyoka.utils.jabber
    ~~~~~~~~~~~~~~~~~~~

    Helper functions to communicate with the bot.  The communication uses
    basic XMLRPC.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import re
from inyoka.conf import settings
from inyoka.tasks import send_jabber


#XXX: according to rfc4622 a nodeid is optional. But we require one
#     'cause nobody should enter a service-jid in the jabber field.
#     Should we permit or deny? If we permit we need to validate the
#     domain and resid!
_jabber_re = re.compile(r'(?xi)(?:[a-z0-9!$\(\)*+,;=\[\\\]\^`{|}\-._~]+)@')


def may_be_valid_jabber(jabber):
    return _jabber_re.match(jabber) is not None


def send(jid, message, xhtml=True):
    """
    Send a message to a jid.  `message` must be a valid XHTML document as
    unicode string.  If it's not parseable XHTML an `ValueError` is raised.

    If a raw, non xhtml message is wanted you can set `xhtml` to `False`.

    If the bot is offline this function fails silently and returns `False`,
    otherwise the return value is `True`.
    """
    return send_jabber.delay(jid, message, xhtml)
