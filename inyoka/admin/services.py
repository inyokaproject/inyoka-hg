# -*- coding: utf-8 -*-
"""
    inyoka.admin.services
    ~~~~~~~~~~~~~~~~~~~~~

    Various services for the admin interface.


    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from inyoka.portal.user import User
from inyoka.utils.services import SimpleDispatcher

# The autocompletion for the privmsg is at portal/services.py
def on_get_user_autocompletion(request):
    q = request.GET.get('q', '')
    if len(q) < 3:
        return
    qs = list(User.objects.filter(username__istartswith=q)[:11])
    usernames = [x.username for x in qs]
    if len(qs) > 10:
        usernames[10] = '…'
    return usernames



dispatcher = SimpleDispatcher(
    get_user_autocompletion=on_get_user_autocompletion,
)
