# -*- coding: utf-8 -*-
"""
    inyoka.portal.services
    ~~~~~~~~~~~~~~~~~~~~~~

    Various services for the portal or all applications.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
import md5
from django.conf import settings
from inyoka.portal.user import User
from inyoka.utils.services import SimpleDispatcher
from inyoka.utils import get_random_password
from inyoka.utils.captcha import Captcha


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
    for user in User.objects.exclude(coordinates_long=None) \
                            .exclude(coordinates_lat=None):
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


dispatcher = SimpleDispatcher(
    get_current_user=on_get_current_user,
    get_usermap_markers=on_get_usermap_markers,
    get_random_password=on_get_random_password,
    get_captcha=on_get_captcha
)
