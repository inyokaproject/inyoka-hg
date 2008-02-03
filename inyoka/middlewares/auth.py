#-*- coding: utf-8 -*-
"""
    inyoka.middlewares.auth
    ~~~~~~~~~~~~~~~~~~~~~~~

    This replaces the django auth middleware.

    :copyright: 2008 by Christopher Grebs, Armin Ronacher.
    :license: GNU GPL.
"""
from inyoka.portal.user import User


class AuthMiddleware(object):

    def process_request(self, request):
        try:
            user_id = request.session['uid']
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, KeyError):
            user = User.objects.get_anonymous_user()
        request.user = user
