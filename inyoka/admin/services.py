# -*- coding: utf-8 -*-
"""
    inyoka.admin.services
    ~~~~~~~~~~~~~~~~~~~~~

    Various services for the admin interface.


    :copyright: Copyright 2008 by Armin Ronacher, Christopher Grebs.
    :license: GNU GPL.
"""
from inyoka.portal.user import User
from inyoka.utils.services import SimpleDispatcher


def on_get_user_autocompletion(request):
    q = request.GET.get('q', '')
    if len(q) < 3:
        return
    qs = list(User.objects.filter(username__startswith=q)[:11])
    usernames = [x.username for x in qs]
    if len(qs) > 10:
        usernames[10] = '…'
    return usernames



dispatcher = SimpleDispatcher(
    get_user_autocompletion=on_get_user_autocompletion,
)
