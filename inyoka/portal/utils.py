# -*- coding: utf-8 -*-
"""
    inyoka.portal.utils
    ~~~~~~~~~~~~~~~~~~~

    Utilities for the portal.

    :copyright: 2007 by Benjamin Wiegand, Christopher Grebs, Armin Ronacher.
    :license: GNU GPL, see LICENSE for more details.
"""
from django.http import HttpResponseRedirect
from inyoka.utils.urls import href
from inyoka.utils.flashing import flash


def decor(decorator, base):
    decorator.__name__ = base.__name__
    decorator.__module__ = base.__module__
    decorator.__doc__ = base.__doc__
    return decorator


def check_login(message=None):
    """
    This function can be used as a decorator to check whether the user is
    logged in or not. Also it's possible to send the user a message if
    hes' logged out and needs to login.
    """
    def _wrapper(func):
        def decorator(*args, **kwargs):
            req = args[0]
            if req.user.is_authenticated:
                return func(*args, **kwargs)
            if message is not None:
                flash(message)
            args = {'next': 'http://%s%s' % (req.get_host(), req.path)}
            return HttpResponseRedirect(href('portal', 'login', **args))
        return decor(decorator, func)
    return _wrapper


def require_manager(f):
    """Require that the user is logged in and is a manager."""
    def decorator(request, *args, **kwargs):
        if request.user.is_manager:
            return f(request, *args, **kwargs)
        return abort_access_denied()
    return simple_check_login(decor(decorator, f))


def simple_check_login(f):
    """
    This function can be used as a decorator to check whether the user is
    logged in or not.
    If he is, the decorated function is called normally, else the login page
    is shown without a response to the user.
    """
    def decorator(*args, **kwargs):
        req = args[0]
        if req.user.is_authenticated:
            return f(*args, **kwargs)
        args = {'next': 'http://%s%s' % (req.get_host(), req.path)}
        return HttpResponseRedirect(href('portal', 'login', **args))
    return decor(decorator, f)


def abort_access_denied(request):
    """Abort with an access denied message or go to login."""
    if request.user.is_anonymous:
        args = {'next': 'http://%s%s' % (request.get_host(), request.path)}
        return HttpResponseRedirect(href('portal', 'login', **args))
    return AccessDeniedResponse()
