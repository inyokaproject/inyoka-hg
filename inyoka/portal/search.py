# -*- coding: utf-8 -*-
"""
    inyoka.portal.search
    ~~~~~~~~~~~~~~~~~~~~

    Since the portal doesn't create and store searchable documents by its
    own this module only provides some general customations which are
    available through the whole portal.  For the concrete implementations
    have a look at the `inyoka.app.search` modules, where app is the
    name of the application.

    :copyright: Copyright 2007 by Christoph Hack.
    :license: GNU GPL.
"""
import xapian
from inyoka.portal.user import User
from inyoka.utils.search import search_handler, tokenize


@search_handler(u'user', u'author')
def handle_user(username):
    """Look up the user id for an given given username."""
    try:
        user = User.objects.get(username=username)
        return xapian.Query(u'U%d' % (user.id))
    except User.DoesNotExist:
        return None


@search_handler(u'title', u'titel')
def handle_title(title):
    """Tokenize words in the title automatically."""
    tokens = tokenize(title)
    query = None
    for token in tokens:
        if query is None:
            query = xapian.Query(u'T%s' % token)
        else:
            query = xapian.Query(xapian.Query.OP_AND, query,
                                 xapian.Query(u'T%s'%  token))
    return query


@search_handler(u'area', u'bereich')
def handle_area(area):
    """Normalize the name of the area."""
    map = {
        'forum': 'f',
        'wiki': 'w',
        'ikhaya': 'i',
        'planet': 'p',
    }
    component = map.get(area.strip().lower())
    return component and xapian.Query(u'P%s' % component)

@search_handler(u'category', u'kategorie')
def handle_category(category):
    return xapian.Query(u'C%s' % category.lower())

@search_handler(u'solved', u'gelöst')
def handle_solved(solved):
    try:
        return xapian.Query(u'S%d' % int(solved))
    except:
        return xapian.Query(u'S%d' % bool(solved))

@search_handler(u'version', u'version')
def handle_version(version):
    return xapian.Query(u'V%s' % version.lower())

@search_handler(u'distro', u'Distribution')
def handle_distro(distro):
    return xapian.Query(u'D%s' % distro.lower())
