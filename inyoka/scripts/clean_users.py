#-*- coding: utf-8 -*-
"""
    inyoka.scripts.clean_expired_users
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    A simple script that searches for non activated users whose
    activation key is expired and deletes them.

    :copyright: 2007-2009 by Christopher Grebs.
    :license: GNU GPL.
"""
import sys
from datetime import datetime, timedelta
import time
from inyoka.conf import settings
from inyoka.application import *


def get_expired_users():
    from inyoka.portal.user import User
    current_datetime = datetime.fromtimestamp(time.time())
    delta_to_activate = timedelta(hours=settings.ACTIVATION_HOURS)

    for user in User.objects.filter(status=0):
        if (current_datetime - user.date_joined) > delta_to_activate:
            yield user


def get_inactive_users(excludes=None):
    from inyoka.portal.user import User
    current_datetime = datetime.fromtimestamp(time.time())
    delta = timedelta(days=settings.USER_INACTIVE_DAYS)

    excludes = set(u.id for u in excludes) if excludes else set([])

    for user in User.objects.filter(status=1).exclude(id__in=excludes).all():
        if user.last_login and (current_datetime - user.last_login) < delta:
            continue

        if not user.last_login:
            # there are some users with no last login, set it to a proper value
            user.last_login = current_datetime
            user.save()

        counters = (
            # private messages
            user.privatemessageentry_set.count() > 0,
            # ikhaya articles
            user.article_set.count() > 0,
            # ikhaya article comments
            user.comment_set.count() > 0,
            # pastes
            user.entry_set.count() > 0,
            # created events
            user.event_set.count() > 0,
            # active suggestions to ikhaya articles
            user.suggestion_set.count() > 0,
            # user posts
            user.post_count > 0,
            # user wiki revisions
            user.wiki_revisions.count() > 0,
            # user subscriptions to threads/wikipages etc.
            user.subscription_set.count() > 0
        )

        if not any(counters):
            yield user


if __name__ == '__main__':
    users_to_delete = []
    expired = tuple(get_expired_users())
    inactive = tuple(get_inactive_users())
    print "expired users: %s" % len(expired)
    print "users counted as inactive: %s" % len(inactive)
    print "users deletable: %s" % (len(expired + inactive))
    if '--delete' in sys.argv:
        for user in set((expired + inactive)):
            user.delete()
