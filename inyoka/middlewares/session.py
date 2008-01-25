# -*- coding: utf-8 -*-
"""
    inyoka.middlewares.session
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    A custom version of the session middleware that allows to set the
    session time (permanent, non permanent) on a session basis.  So users
    can decide to have a permanent session on login.

    To control the session system use the `make_permanet` and
    `close_with_browser` functions of the `inyoka.utils.sessions` module.

    Uses client side storage.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
try:
    from hashlib import md5
except ImportError:
    from md5 import md5
from time import time
from random import random
from django.conf import settings
from django.utils.http import cookie_date
from werkzeug.contrib.securecookie import SecureCookie


class Session(SecureCookie):

    @property
    def session_key(self):
        if not 'session_key' in self:
            self['session_key'] = md5('%s%s%s' % (random(), time(),
                                      settings.SECRET_KEY)).hexdigest()
        return self['session_key']


class AdvancedSessionMiddleware(object):
    """
    Session middleware that allows you to turn individual browser-length
    sessions into persistent sessions and vice versa.

    This middleware can be used to implement the common "Remember Me" feature
    that allows individual users to decide when their session data is discarded.
    If a user ticks the "Remember Me" check-box on your login form create
    a persistent session, if they don't then create a browser-length session.
    """

    def process_request(self, request):
        data = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
        if data:
            session = Session.unserialize(data, settings.SECRET_KEY)
        else:
            session = Session(secret_key=settings.SECRET_KEY)
        request.session = session

    def process_response(self, request, response):
        try:
            modified = request.session.modified
        except AttributeError:
            return response

        if modified or settings.SESSION_SAVE_EVERY_REQUEST:
            if request.session.get('is_permanent_session'):
                max_age = settings.SESSION_COOKIE_AGE
                expires_time = time() + settings.SESSION_COOKIE_AGE
                expires = cookie_date(expires_time)
            else:
                max_age = expires = None
            response.set_cookie(settings.SESSION_COOKIE_NAME,
                                request.session.serialize(),
                                max_age=max_age, expires=expires,
                                domain=settings.SESSION_COOKIE_DOMAIN,
                                secure=settings.SESSION_COOKIE_SECURE or None)
        return response
