# -*- coding: utf-8 -*-
"""
    inyoka.utils.jabber
    ~~~~~~~~~~~~~~~~~~~

    Helper functions to communicate with the bot.  The communication uses
    basic XMLRPC.

    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
import socket
from xmlrpclib import ServerProxy, Fault
from django.conf import settings


_proxy = None


def send(jid, message, xhtml=True):
    """
    Send a message to a jid.  `message` must be a valid XHTML document as
    unicode string.  If it's not parseable XHTML an `ValueError` is raised.

    If a raw, non xhtml message is wanted you can set `xhtml` to `False`.

    If the bot is offline this function fails silently and returns `False`,
    otherwise the return value is `True`.
    """
    global _proxy
    if _proxy is None:
        _proxy = ServerProxy('http://%s/' % settings.JABBER_BOT_SERVER)
    try:
        (_proxy.jabber.sendMessage, _proxy.jabber.sendRawMessage) \
        [not xhtml](jid, message)
    except Fault, e:
        raise ValueError(e.faultString)
    except socket.error:
        return False
    return True
