# -*- coding: utf-8 -*-
"""
    inyoka.portal.utils
    ~~~~~~~~~~~~~~~~~~~

    Utilities for the portal.

    :copyright: 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import calendar
from datetime import date
from django.db.models import Q

from inyoka.utils.urls import href
from inyoka.utils.decorators import patch_wrapper
from inyoka.utils.flashing import flash
from inyoka.utils.http import AccessDeniedResponse, HttpResponseRedirect


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


def calendar_entries_for_month(year, month):
    """
    Return a list with all days in a month and the calendar entries grouped
    by day (also make an entry in the list if there is no event)
    """
    from inyoka.portal.models import Event
    days = {}
    month_range = range(1, calendar.monthrange(year, month)[1] + 1)
    for i in month_range:
        days[i] = []
    start_date = date(year=year, month=month, day=month_range[0])
    end_date = date(year=year, month=month, day=month_range[-1])
    events = Event.objects.filter(
        Q(date__range=(start_date, end_date)) |
        Q(duration__range=(start_date, end_date))).all()

    for event in events:
        if event.duration is not None:
            if event.date < start_date:
                delta = event.duration.date() - start_date
                base = start_date.day
            else:
                delta = event.duration.date() - event.date
                base = event.date.day
            for day in range(delta.days+1):
                if base + day in days:
                    days[base+day].append(event)
        else:
            days[event.date.day].append(event)
    return days
