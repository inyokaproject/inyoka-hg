# -*- coding: utf-8 -*-
"""
    inyoka.forum.acl
    ~~~~~~~~~~~~~~~~

    Authentification systen for the forum.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL, see LICENSE for more details.
"""
from itertools import izip
from django.db import connection
from inyoka.portal.user import User, Group, DEFAULT_GROUP_ID
from inyoka.forum.models import Forum
from inyoka.utils.decorators import patch_wrapper
from inyoka.utils.search import search


PRIVILEGES_DETAILS = [
    ('void', 'darf nix'),
    ('read', 'kann lesen'),
    ('reply', 'kann antworten'),
    ('create', 'kann erstellen'),
    ('edit', 'kann bearbeitenen'),
    ('revert', 'kann revidieren'),
    ('delete', u'kann löschen'),
    ('sticky', 'kann anpinnen'),
    ('vote', 'kann abstimmen'),
    ('create_poll', 'kann Umfragen erstellen'),
    ('upload', u'kann Anhänge nutzen'),
    ('moderate', 'kann moderieren')
]

PRIVILEGES = [x[0] for x in PRIVILEGES_DETAILS]


def get_forum_privileges(user, forum):
    """Get a dict of all the privileges for a user."""
    return get_privileges(user, [forum])[forum.id]


def get_privileges(user, forums):
    """Return all privileges of the applied forums for the `user`"""
    forum_ids = [x.id for x in forums]
    if not forum_ids:
        return dict.fromkeys(PRIVILEGES, False)
    fields = ', '.join('p.can_' + x for x in PRIVILEGES)
    cur = connection.cursor()
    cur.execute('''
        select p.forum_id, %s
          from forum_privilege p, portal_user u
         where p.forum_id in (%s) and (p.user_id = %%s or p.group_id in
               (select g.id from portal_group g, portal_user u,
                                 portal_user_groups ug
                 where u.id = ug.user_id and g.id = ug.group_id)
               %s)
    ''' % (fields, ', '.join(['%s'] * len(forum_ids)),
        user.is_authenticated and 'or p.group_id = %d' % DEFAULT_GROUP_ID or ''),
        (tuple(forum_ids) + (user.id,)))
    result = {}
    for forum_id in forum_ids:
        result[forum_id] = dict.fromkeys(PRIVILEGES, False)
    for row in cur.fetchall():
        for key, item in izip(PRIVILEGES, row[1:]):
            if item:
                result[row[0]][key] = True
    return result


def have_privilege(user, forum, privilege):
    """Check if a user has a privilege on a resource."""
    return bool(get_forum_privileges(user, forum).get(privilege, False))


def filter_invisible(user, forums, priv='read'):
    """Filter all forums where the user has a privilege on it."""
    privileges = get_privileges(user, forums)
    result = []
    for forum in forums:
        if privileges.get(forum.id, {priv: False})[priv]:
            result.append(forum)
    return result
