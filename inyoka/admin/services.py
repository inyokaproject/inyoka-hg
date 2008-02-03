# -*- coding: utf-8 -*-
"""
    inyoka.admin.services
    ~~~~~~~~~~~~~~~~~~~~~

    Various services for the admin interface.


    :copyright: Copyright 2008 by Armin Ronacher, Christopher Grebs.
    :license: GNU GPL.
"""
from inyoka.portal.user import User, Group
from inyoka.utils.services import SimpleDispatcher


def on_get_user_autocompletion(request):
    qs = list(User.objects.filter(username__startswith=
                                  request.GET.get('q', ''))[:11])
    if len(qs) > 10:
        qs[10] = '...'
    return [u.username for u in qs]


def on_get_group_autocompletition(request):
    qs = list(Group.objects.filter(username__startswith=
                                   request.GET.get('q', '')))
    return [g.name for g in qs]


dispatcher = SimpleDispatcher(
    get_user_autocompletion=on_get_user_autocompletion,
    get_group_autocompletition=on_get_group_autocompletition
)
