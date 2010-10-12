# -*- coding: utf-8 -*-
"""
    inyoka.forum.acl
    ~~~~~~~~~~~~~~~~

    Authentification systen for the forum.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from inyoka.utils.database import db
from inyoka.utils.cache import cache


PRIVILEGES_DETAILS = [
    ('read', 'kann lesen'),
    ('vote', 'kann abstimmen'),
    ('create', 'kann Themen erstellen'),
    ('reply', 'kann antworten'),
    ('upload', u'kann Anhänge erstellen'),
    ('create_poll', 'kann Umfragen erstellen'),
    ('sticky', 'kann Themen anpinnen'),
    ('moderate', 'kann moderieren')
]

PRIVILEGES = [x[0] for x in PRIVILEGES_DETAILS]
PRIVILEGES_BITS = dict((PRIVILEGES[i-1], 2**i)
                       for i in xrange(1, len(PRIVILEGES_DETAILS) + 1))
REVERSED_PRIVILEGES_BITS = dict((y,x) for x,y in PRIVILEGES_BITS.iteritems())

#: create some constants for easy access
g = globals()
for desc, bits in PRIVILEGES_BITS.iteritems():
    g['CAN_%s' % desc.upper()] = bits
DISALLOW_ALL = 0

del desc, bits


def join_flags(*flags):
    """
    Small helper function for the admin-panel
    to join some flags to one bit-mask.
    """
    if not flags:
        return DISALLOW_ALL
    result = DISALLOW_ALL
    for flag in flags:
        if isinstance(flag, basestring):
            flag = PRIVILEGES_BITS[flag]
        if flag == 0:
            return 0
        result |= flag
    return result


def split_bits(mask=None):
    """
    Return an iterator with all bits splitted
    from the `mask`.
    """
    if mask is None:
        return
    for desc, bits in PRIVILEGES_BITS.iteritems():
        if mask & bits != 0:
            yield bits


def get_forum_privileges(user, forum_id):
    """Get a dict of all the privileges for a user."""
    return get_privileges(user, forum_ids=[forum_id])[forum_id]


def _get_privilege_map(user, forum_ids):
    ug = user_group_table.c
    groups = db.select([ug.group_id], ug.user_id == user.id)

    P = Privilege
    cols = (P.forum_id, P.positive, P.negative, P.user_id)

    # construct the query, but do not execute it yet for caching reasons
    query = db.session.query(*cols).filter(db.and_(
        db.or_(Privilege.user_id == user.id,
               Privilege.group_id.in_(groups),
               Privilege.group_id == (user.is_anonymous and -1 or DEFAULT_GROUP_ID))
    ))

    # If we have an anonymous user we can cache the results
    # We do that for all forums, this makes it possible to cache the privileges.
    # Once we get an authenticated user we filter for the ids requested.
    cache_key = 'forum/acls/anonymous'
    if user.is_anonymous:
        result = cache.get(cache_key)
        if result is None:
            privilege_map = query.all()
            cache.set(cache_key, privilege_map, 86400)
        else:
            privilege_map = list(query.merge_result(result, False))
        # filter the privilege_map for ids not requested (api compatibility)
        privilege_map = [row for row in privilege_map if row.forum_id in forum_ids]
    else:
        # we filter for the privilege ids if we don't have an anonymous user
        all_ids = Forum.query.get_ids()
        # Do only filter IN if required.  This is not required most of the time
        # so that this saves a bit bandwith and quite a few time for the query
        if len(forum_ids) != len(all_ids):
            query = query.filter(Privilege.forum_id.in_(forum_ids))
        privilege_map = query.all()

    return privilege_map


def get_privileges(user, forum_ids):
    """Return all privileges of the applied forums for the `user`"""
    if not forum_ids:
        return {}

    privilege_map = _get_privilege_map(user, forum_ids)

    def join_bits(result, rows):
        """
        Join the positive bits of all forums and subtract the negative ones of
        them.
        """
        negative = dict(map(lambda a: (a, set()), forum_ids))
        for forum_id, p, n, _ in rows:
            result[forum_id] |= p
            negative[forum_id].add(n)
        for forum_id, bits in negative.iteritems():
            for bit in bits:
                if result[forum_id] & bit:
                    result[forum_id] -= bit
        return result

    result = dict(map(lambda a: (a, DISALLOW_ALL), forum_ids))
    # first join the group privileges
    result = join_bits(result, [row for row in privilege_map if not row.user_id])
    # now join the user privileges (this allows to override group privileges)
    result = join_bits(result, [row for row in privilege_map if row.user_id])
    return result


def have_privilege(user, obj, privilege):
    """Check if a user has a privilege on a forum or a topic."""
    if isinstance(privilege, basestring):
        privilege = PRIVILEGES_BITS[privilege]
    if hasattr(obj, 'forum_id'):
        # obj is a topic
        forum_id = obj.forum_id
    else:
        # obj is a forum
        forum_id = obj.id
    return get_forum_privileges(user, forum_id) & privilege != 0


def check_privilege(mask, privilege):
    """
    Check for an privilege on an existing mask.
    Note: This does not touch the database so use
    this as much as possible instead of many
    `have_privilege` statements.

    `mask`
        The Bit-mask representing all forum-privileges
    `privilege`
        A string or Bit-mask representing one privilege
    """
    if isinstance(privilege, basestring):
        privilege = PRIVILEGES_BITS[privilege]
    return mask & privilege != 0


def filter_invisible(user, forums=None, priv=CAN_READ, privileges=None):
    """Filter all forums where the user has a privilege on it."""
    forums = forums or []
    privileges = privileges or get_privileges(user, [f.id for f in forums])
    result = []
    for forum in forums:
        if privileges.get(forum.id, DISALLOW_ALL) & priv != 0:
            result.append(forum)
    return result


def filter_visible(user, forums=None, priv=CAN_READ, privileges=None):
    forums = forums or []
    privileges = privileges or get_privileges(user, [f.id for f in forums])
    result = []
    for forum in forums:
        if privileges.get(forum.id, DISALLOW_ALL) & priv == 0:
            result.append(forum)
    return result


# circular imports
from inyoka.forum.models import Privilege, Forum
from inyoka.forum.compat import user_group_table
from inyoka.portal.user import DEFAULT_GROUP_ID
