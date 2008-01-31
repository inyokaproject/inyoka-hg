# -*- coding: utf-8 -*-
"""
    inyoka.form.acl
    ~~~~~~~~~~~~~~~

    Authentification systen for the forum.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL, see LICENSE for more details.
"""
from itertools import izip
from django.db import connection
from inyoka.portal.user import User, Group
from inyoka.forum.models import Forum
from inyoka.portal.utils import decor
from inyoka.utils.search import search


PRIVILEGES = ['read', 'reply', 'create', 'edit', 'revert', 'delete',
              'sticky', 'vote', 'create_poll', 'upload', 'moderate']

PRIVILEGES_DETAILS = [
    ('read', 'kann lesen'),
    ('reply', 'kann antworten'),
    ('create', 'kann Erstellen'),
    ('edit', 'kann editieren'),
    ('revert', 'kann revidieren'),
    ('delete', 'kann löschen'),
    ('sticky', 'kann anpinnen'),
    ('vote', 'kann voten'),
    ('create', 'kann Umfragen erstellen'),
    ('upload', 'kann Attachments nutzen'),
    ('moderate', 'kann moderieren')
]


def get_forum_privileges(user, forum):
    """Get a dict of all the privileges for a user."""
    return get_privileges(user, [forum])[forum.id]


def get_privileges(user, forums):
    """Return all privileges of the applied forums for the `user`"""
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


class SearchAuthDecider(object):
    """Decides whetever a user can display a search result or not."""

    def __init__(self, user):
        privs = get_privileges(user, Forum.objects.all())
        self.privs = dict((key, priv['read']) for key, priv in privs.iteritems())
        print self.privs

    def call(self, doc):
        return self.privs.get(int(doc.get_value(0).split(':')[1]), False)

search.register_auth_decider('f', SearchAuthDecider)
