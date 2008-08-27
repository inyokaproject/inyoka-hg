# -*- coding: utf-8 -*-
"""
    inyoka.portal.services
    ~~~~~~~~~~~~~~~~~~~~~~

    Various services for the portal or all applications.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
import md5
import time
from urlparse import urlparse
from inyoka.conf import settings
from inyoka.portal.user import User
from inyoka.portal.models import Event
from inyoka.utils.text import get_random_password
from inyoka.utils.http import PageNotFound, HttpResponseRedirect
from inyoka.utils.dates import MONTHS, WEEKDAYS
from inyoka.utils.services import SimpleDispatcher
from inyoka.utils.captcha import Captcha
from inyoka.utils.templating import render_template
from inyoka.utils.xmlrpc import xmlrpc
from inyoka.utils.urls import href


def on_get_current_user(request):
    """Get the current user."""
    user = request.user
    return {
        'is_anonymous':     user.is_anonymous,
        'username':         user.username or None,
        'email':            getattr(user, 'email', None),
    }


def on_get_usermap_markers(request):
    """Return markers for the usermap."""
    markers = []
    for user in User.objects.filter(coordinates_long__isnull=False,
                                    coordinates_lat__isnull=False):
        long = user.coordinates_long
        lat = user.coordinates_lat
        markers.append({
            'type':     'user',
            'detail': {
                'user_id':      user.id,
                'username':     user.username
            },
            'pos':      (lat, long)
        })
    return {'markers': markers}


def on_get_random_password(request):
    return {'password': get_random_password()}


def on_get_captcha(request):
    captcha = Captcha()
    h = md5.new(settings.SECRET_KEY)
    h.update(captcha.solution)
    request.session['captcha_solution'] = h.digest()
    return captcha.get_response()


def on_get_calendar_entry(request):
    if 'url' in request.GET:
        url = request.GET['url']
        slug = urlparse(url)[2][10:]
        if slug.endswith('/'):
            slug = slug[:-1]
    else:
        try:
            slug = request.GET['slug']
        except KeyError:
            raise PageNotFound
    try:
        event = Event.objects.get(slug=slug)
    except Event.DoesNotExist:
        raise PageNotFound

    data = {
        'event': event,
        'MONTHS': dict(list(enumerate(MONTHS))[1:]),
        'WEEKDAYS': dict(enumerate(WEEKDAYS)),
    }
    return render_template('portal/_calendar_detail.html', data)


def on_toggle_sidebar(request):
    if not request.user.is_authenticated:
        return False
    if request.GET.get('hide') == 'true':
        request.user.settings['sidebar_hidden'] = True
    else:
        request.user.settings.pop('sidebar_hidden')
    request.user.save()
    return True


def hide_global_message(request):
    if request.user.is_authenticated:
        request.user.settings['global_message_hidden'] = time.time()
        request.user.save()
        return True
    return False


dispatcher = SimpleDispatcher(
    get_current_user=on_get_current_user,
    get_usermap_markers=on_get_usermap_markers,
    get_random_password=on_get_random_password,
    get_captcha=on_get_captcha,
    get_calendar_entry=on_get_calendar_entry,
    toggle_sidebar=on_toggle_sidebar,
    xmlrpc=xmlrpc, hide_global_message=hide_global_message
)
