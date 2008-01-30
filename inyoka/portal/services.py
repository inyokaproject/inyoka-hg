# -*- coding: utf-8 -*-
"""
    inyoka.portal.services
    ~~~~~~~~~~~~~~~~~~~~~~

    Various services for the portal or all applications.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from inyoka.portal.user import User
from inyoka.utils.services import SimpleDispatcher
from inyoka.utils import get_random_password


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
    for user in User.objects.exclude(coordinates=''):
        try:
            parts = user.coordinates.split(',')
            lat = float(parts[0].strip())
            long = float(parts[1].strip())
        except (ValueError, IndexError, TypeError):
            user.coordinates = ''
            user.save()
            continue
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


dispatcher = SimpleDispatcher(
    get_current_user=on_get_current_user,
    get_usermap_markers=on_get_usermap_markers,
    get_random_password=on_get_random_password,
)
