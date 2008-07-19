# -*- coding: utf-8 -*-
"""
    inyoka.portal.utils
    ~~~~~~~~~~~~~~~~~~~

    Utilities for the portal.

    :copyright: 2008 by Benjamin Wiegand, Christopher Grebs, Armin Ronacher.
    :license: GNU GPL, see LICENSE for more details.
"""
import random
import string
import calendar
from md5 import new as md5
from inyoka.conf import settings
from inyoka.utils.urls import href
from inyoka.utils.decorators import patch_wrapper
from inyoka.utils.flashing import flash
from inyoka.utils.http import AccessDeniedResponse, HttpResponseRedirect
from inyoka.utils.templating import render_template


def check_login(message=None):
    """
    This function can be used as a decorator to check whether the user is
    logged in or not.  Also it's possible to send the user a message if
    he's logged out and needs to login.
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
        return patch_wrapper(decorator, func)
    return _wrapper


def require_permission(*perms):
    """
    This decorator checks whether the user has a special permission and
    raises 403 if he doesn't. If you pass more than one permission name,
    the view function is executed if the user has one of them.
    """
    def f1(func):
        def f2(request, *args, **kwargs):
            for perm in perms:
                if request.user.can(perm):
                    return func(request, *args, **kwargs)
            return abort_access_denied(request)
        return f2
    return f1


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
    return patch_wrapper(decorator, f)


def abort_access_denied(request):
    """Abort with an access denied message or go to login."""
    if request.user.is_anonymous:
        args = {'next': 'http://%s%s' % (request.get_host(), request.path)}
        return HttpResponseRedirect(href('portal', 'login', **args))
    return AccessDeniedResponse()


def gen_activation_key(user):
    """
    Create a new activation key.
    It's a md5 hash from the user id, the username,
    the users email and our secret key.

    :Parameters:
        user
            An user object from the user the key
            will be generated for.
    """
    return md5('%d%s%s%s' % (
        user.id, user.username.encode('utf-8'),
        settings.SECRET_KEY,
        user.email.encode('utf-8')
    )).hexdigest()


def check_activation_key(user, key):
    """
    Check if an activation key is correct

    :Parameters:
        user
            An user object a new key will be generated for.
            (For checking purposes)
        key
            The key that needs to be checked for the *user*.
    """
    return key == gen_activation_key(user)


def send_activation_mail(user):
    """send an activation mail"""
    from inyoka.utils.mail import send_mail
    message = render_template('mails/activation_mail.txt', {
        'username':         user.username,
        'email':            user.email,
        'activation_key':   gen_activation_key(user)
    })
    send_mail('Aktivierung des Benutzers %s'
              % user.username,
              message, settings.INYOKA_SYSTEM_USER_EMAIL, [user.email])


def send_new_user_password(user):
    from inyoka.utils.mail import send_mail
    new_password_key = ''.join(random.choice(string.lowercase + string.digits)
                               for _ in range(24))
    user.new_password_key = new_password_key
    user.save()
    message = render_template('mails/new_user_password.txt', {
        'username':         user.username,
        'email':            user.email,
        'new_password_url': href('portal', 'lost_password',
                                 user.username, new_password_key),
    })
    send_mail(u'ubuntuusers.de – Neues Passwort für %s' % user.username,
              message, settings.INYOKA_SYSTEM_USER_EMAIL, [user.email])


def calendar_entries_for_month(year, month):
    """
    Return a list with all days in a month and the calendar entries grouped
    by day (also make an entry in the list if there is no event)
    """
    from inyoka.portal.models import Event
    days = {}
    for i in range(1, calendar.monthrange(year, month)[1] + 1):
        days[i] = []
    events = Event.objects.filter(date__year=year, date__month=month)
    for event in events:
        days[event.date.day].append(event)
    return days
