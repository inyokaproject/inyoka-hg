#-*- coding: utf-8 -*-
"""
    inyoka.scripts.clean_expired_users
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    A simple script that searches for non activated users whose
    activation key is expired and deletes them.

    :copyright: 2007 by Christopher Grebs.
    :license: GNU GPL.
"""
from datetime import datetime, timedelta
import time
from inyoka.conf import settings


def get_expired_users():
    from inyoka.portal.user import User
    current_datetime = datetime.fromtimestamp(time.time())
    delta_to_activate = timedelta(hours=settings.ACTIVATION_HOURS)

    for user in User.objects.filter(is_active=False):
        if (current_datetime - user.date_joined) > delta_to_activate:
            yield user


if __name__ == '__main__':
    users = get_expired_users()
    count = 0
    for count, user in enumerate(users):
        user.delete()
    print "deleted %d users." % count
