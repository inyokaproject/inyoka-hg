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
from inyoka.portal.user import DEFAULT_GROUP_ID


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

PRIVILEGES = [x[0] for x in PRIVILEGES_DETAILS[1:]]
PRIVILEGES_BITS = dict((PRIVILEGES[i-1], 2**i) for i in xrange(1, 12))
REVERSED_PRIVILEGES_BITS = dict((y,x) for x,y in PRIVILEGES_BITS.iteritems())

#: create some constants for easy access
g = globals()
for desc, bits in PRIVILEGES_BITS.iteritems():
    g['CAN_%s' % desc.upper()] = bits
PRIVILEGES_BITS['void'] = DISALLOW_ALL = 0


def join_flags(*flags):
    """
    Small helper function for the admin-panel
    to join some flags to one bit-mask.
    """
    if not flags:
        return DISALLOW_ALL
    result = DISALLOW_ALL
    for flag in flags:
        result |= isinstance(flag, basestring) and \
                  PRIVILEGES_BITS[flag] or flag
    return result


def split_flags(mask=None):
    """
    Return an iterator with all flags splitted
    from the `mask`.
    The flags are represented by a small string
    as defined in PRIVILEGES_DETAILS
    """
    if mask is None:
        return
    for desc, bits in PRIVILEGES_BITS.iteritems():
        if mask & bits != 0:
            yield desc


def get_forum_privileges(user, forum_id):
    """Get a dict of all the privileges for a user."""
    return get_privileges(user, forum_ids=[forum_id])[forum_id]


def get_privileges(user, forum_ids):
    """Return all privileges of the applied forums for the `user`"""
    if not forum_ids:
        return {}
    cur = connection.cursor()
    cur.execute('''
        select p.forum_id, p.bits
          from forum_privilege p, portal_user u
         where p.forum_id in (%s) and (p.user_id = %d or p.group_id in
               (select g.id from portal_group g, portal_user u,
                                 portal_user_groups ug
                where u.id = ug.user_id and g.id = ug.group_id)
            %s)
    ''' % (', '.join(map(str, forum_ids)), user.id,
           user.is_authenticated and 'or p.group_id = %d' % DEFAULT_GROUP_ID or ''))

    r = cur.fetchall()
    result = dict.fromkeys(forum_ids, DISALLOW_ALL)
    for row in r:
        result[row[0]] = row[1]
    return result


def have_privilege(user, forum, privilege):
    """Check if a user has a privilege on a resource."""
    return get_forum_privileges(user, forum.id) & privilege != 0


def check_privilege(mask, privilege):
    if isinstance(privilege, basestring):
        return mask & PRIVILEGES_BITS[privilege]
    return mask & privilege


def filter_invisible(user, forums, priv=CAN_READ):
    """Filter all forums where the user has a privilege on it."""
    privileges = get_privileges(user, [f.id for f in forums])
    result = []
    for forum in forums:
        if privileges.get(forum.id, DISALLOW_ALL) & priv != 0:
            result.append(forum)
    return result
