#-*- coding: utf-8 -*-
"""
    inyoka.middlewares.auth
    ~~~~~~~~~~~~~~~~~~~~~~~

    This replaces the django auth middleware.

    :copyright: 2008 by Christopher Grebs.
    :license: GNU GPL.
"""
from inyoka.utils.user import get_user


class LazyUser(object):
    def __get__(self, request, obj_type=None):
        if not hasattr(request, '_cached_user'):
            from inyoka.utils.user import get_user
            request._cached_user = get_user(request)
        return request._cached_user


class AuthMiddleware(object):
    def process_request(self, request):
        request.__class__.user = LazyUser()
        return None
