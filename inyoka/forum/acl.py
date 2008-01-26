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


PRIVILEGES = ['read', 'reply', 'create', 'edit', 'revert', 'delete',
              'sticky', 'vote', 'upload']


def get_privileges(user, forum):
    """Get a dict of all the privileges for a user."""
    fields = ', '.join('p.can_' + x for x in PRIVILEGES)
    cur = connection.cursor()
    cur.execute('''
        select %s
          from forum_privilege p, portal_user u
         where p.forum_id = %%s and (p.user_id = %%s or p.group_id in
               (select g.id from portal_group g, portal_user u,
                                 portal_user_groups ug
                 where u.id = ug.user_id and g.id = ug.group_id))
    ''' % fields, (user.id, forum.id))
    result = dict.fromkeys(PRIVILEGES, False)
    for row in cur.fetchall():
        for key, item in izip(PRIVILEGES, row):
            if item:
                result[key] = True
    return result


def have_privilege(user, forum, privilege):
    """Check if a user has a privilege on a resource."""
    return privilege in get_privileges(user, forum)
