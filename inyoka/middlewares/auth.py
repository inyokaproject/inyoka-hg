#-*- coding: utf-8 -*-
"""
    inyoka.middlewares.auth
    ~~~~~~~~~~~~~~~~~~~~~~~

    This replaces the django auth middleware.

    :copyright: 2008 by Christopher Grebs, Armin Ronacher.
    :license: GNU GPL.
"""
from inyoka.portal.user import User
from inyoka.utils.flashing import flash
from inyoka.utils.html import escape


class AuthMiddleware(object):

    def process_request(self, request):
        try:
            user_id = request.session['uid']
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, KeyError):
            user = User.objects.get_anonymous_user()

        # check for bann
        if user.banned:
            flash((u'Du wurdest ausgeloggt, da der Benutzer „%s“ '
                   u'gerade gebannt wurde' % escape(user.username)), False,
                   session=request.session)

            request.session.pop('uid', None)
            user = User.objects.get_anonymous_user()

        request.user = user
