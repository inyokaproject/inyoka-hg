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


def get_inactive_users():
    from inyoka.portal.user import User
    current_datetime = datetime.fromtimestamp(time.time())
    delta = timedelta(days=settings.USER_INACTIVE_DAYS)

    for user in User.objects.filter(is_active=True):
        if not (current_datetime - user.last_login) > delta:
            continue

        comments = user.comment_set.values()
        wrevisions = user.wiki_revisions.values()
        if not comments and not wrevisions and not user.post_count > 0L:
            yield user


if __name__ == '__main__':
    ecount = 0
    for ecount, user in enumerate(get_expired_users()):
        user.delete()
    print "deleted %d expired user accounts" % ecount
    icount = 0
    for icount, user in enumerate(get_inactive_users()):
        user.delete()
    print "deleted %d inactive user accounts" % icount
