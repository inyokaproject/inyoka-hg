# -*- coding: utf-8 -*-
"""
    inyoka.form.acl
    ~~~~~~~~~~~~~~~

    Auth foo for forum.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL, see LICENSE for more details.
"""
from itertools import izip
from django.db import connection
from inyoka.portal.user import User, Group
from inyoka.forum.models import Forum
from inyoka.portal.utils import decor


PRIVILEGES = ['read', 'reply', 'create', 'edit', 'revert', 'delete',
              'sticky', 'vote', 'create_poll', 'upload', 'moderate']


def get_forum_privileges(user, forum):
    """Get a dict of all the privileges for a user."""
    return get_privileges(user, [forum])[forum.id]


def get_privileges(user, forums):
    if not forums:
        return {}
    forum_ids = [x.id for x in forums]
    fields = ', '.join('p.can_' + x for x in PRIVILEGES)
    cur = connection.cursor()
    cur.execute('''
        select p.forum_id, %s
          from forum_privilege p, portal_user u
         where p.forum_id in (%s) and (p.user_id = %%s or p.group_id in
               (select g.id from portal_group g, portal_user u,
                                 portal_user_groups ug
                 where u.id = ug.user_id and g.id = ug.group_id))
    ''' % (fields, ', '.join(['%s'] * len(forum_ids))),
        (tuple(forum_ids) + (user.id,)))
    result = {}
    for row in cur.fetchall():
        if row[0] not in result:
            result[row[0]] = dict.fromkeys(PRIVILEGES, False)
        for key, item in izip(PRIVILEGES, row[1:]):
            if item:
                result[row[0]][key] = True
    return result


def have_privilege(user, forum, privilege):
    """Check if a user has a privilege on a resource."""
    return privilege in get_forum_privileges(user, forum)


def filter_invisible(user, forums, priv='read'):
    """Filter a user."""
    privileges = get_privileges(user, forums)
    result = []
    for forum in forums:
        if privileges.get(forum.id, {priv: False})[priv]:
            result.append(forum)
    return result
