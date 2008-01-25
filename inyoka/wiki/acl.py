# -*- coding: utf-8 -*-
"""
    inyoka.wiki.acl
    ~~~~~~~~~~~~~~~

    This module handles security levels for the wiki. The system uses the
    wiki storage to store the patterns. Whenever the data is loaded from the
    wiki pages that hold access control information the `storage` module
    splits the data already into easy processable data.

    This is an important detail because the ACL module knows nothing about the
    names of the privileges on the frontend. Internally the names of the
    privileges are mapped to integer flags.

    All previlege functions consume either the privilege flags or the internal
    short name of the privilege. The shortnames are specified in the
    `privilege_map` dict and different from the user interface which uses
    translated versions of the variables.

    Because metadata is part of a page the views have to check if the metadata
    changed in a way the user is not allowed to change it. This module
    provides a function called `test_changes_allowed` that checks for that.


    :copyright: Copyright 2007 by Armin Ronacher, Benjamin Wiegand.
    :license: GNU GPL.
"""
from inyoka.portal.user import User, AnonymousUser
from django.http import HttpResponseRedirect
from inyoka.utils.urls import href
from inyoka.utils.http import AccessDeniedResponse
from inyoka.wiki.storage import storage


#: metadata users without the `PRIV_MANAGE` privilege can edit.
LENIENT_METADATA_KEYS = set(['X-Link', 'X-Attach', 'X-Redirect'])


#: the internal privilege representations. because we try to keep
#: the interface as fast as possible the privilegs are bit fields and
#: not python sets.
PRIV_READ = 1
PRIV_EDIT = 2
PRIV_CREATE = 4
PRIV_ATTACH = 8
PRIV_DELETE = 16
PRIV_MANAGE = 32
PRIV_ATTACH_DANGEROUS = 64

#: keep this updated when adding privileges
PRIV_NONE = 0
PRIV_DEFAULT = PRIV_ALL = 63

#: because we use different names in the german frontend these
#: constants hold the name used in the frontend.
GROUP_ALL = 'Alle'
GROUP_REGISTERED = 'Registriert'
GROUP_UNREGISTERED = 'Unregistriert'
GROUP_OWNER = 'Besitzer'

#: used by the decorator
privilege_map = {
    'read':         PRIV_READ,
    'edit':         PRIV_EDIT,
    'create':       PRIV_CREATE,
    'attach':       PRIV_ATTACH,
    'delete':       PRIV_DELETE,
    'manage':       PRIV_MANAGE
}


class PrivilegeTest(object):
    """
    An instance of this class is passed to all the action templates. Attribute
    access can then be used to check if the current user has a privilege the
    current page.
    """

    jinja_allowed_attributes = privilege_map.keys()

    def __init__(self, user, page_name):
        self._user = user
        self._page_name = page_name
        self._privilege_cache = None

    def __getattr__(self, name):
        if self._privilege_cache is None:
            self._privilege_cache = get_privileges(self._user, self._page_name)
        return self._privilege_cache.get(name, False)


class GroupContainer(object):
    """
    This class fetches the groups for an user in a lazy way. This is used by
    the `get_privilege_flags` to not load groups if they are not used for a
    specific query.

    Use it with the in-Operator:

    >>> groups = GroupContainer(user, 'Main_Page')
    >>> 'All' in groups
    True
    >>> 'something' in groups
    False
    """

    def __init__(self, user, page_name):
        self.user = user
        self.page = page_name
        self.cache = None
        self.extra = set([GROUP_ALL, user.is_authenticated() and
                          GROUP_REGISTERED or GROUP_UNREGISTERED])

    def load(self):
        """Load the data from the database."""
        from inyoka.wiki.models import Page
        self.cache = set(x['name'] for x in self.user.groups.values('name'))
        for item in Page.objects.get_owners(self.page):
            if item == self.user.username or \
               (item.startswith('@') and item[1:] in self.cache):
                self.cache.add(GROUP_OWNER)
                break

    def __contains__(self, obj):
        if obj in self.extra:
            return True
        if self.cache is None:
            self.load()
        return obj in self.cache


def get_privilege_flags(user, page_name):
    """
    Return an integer with the privilege flags for a user for the given
    page name. Like any other page name depending function the page name
    must be in a normalized state.
    """
    if user is None:
        user = AnonymousUser()
    elif isinstance(user, basestring):
        user = User.objects.get(username=user)
    groups = GroupContainer(user, page_name)

    rules = storage.acl
    if not rules:
        return PRIV_DEFAULT
    privileges = PRIV_NONE
    for pattern, subject, add_privs, del_privs in rules:
        if ((subject == user.username or
             subject.startswith('@') and subject[1:] in groups)) and \
             pattern.match(page_name) is not None:
            privileges = (privileges | add_privs) & ~del_privs
    return privileges


def get_privileges(user, page_name):
    """
    Get a dict with the privileges a user has for a page (or doesn't).  `user`
    must be a user object or `None` in which case the privileges for an
    anonymous user are returned.
    """
    result = {}
    flags = get_privilege_flags(user, page_name)
    for name, flag in privilege_map.iteritems():
        result[name] = (flags & flag) != 0
    return result


def has_privilege(user, page_name, privilege):
    """
    Check if a user has a special privilege on a page. If you want to check
    for multiple privileges (for example if you want to display what a user
    can do or not do) you should use `get_privileges` which is faster for
    multiple checks and also returns it automatically as a dict.
    """
    if isinstance(privilege, basestring):
        privilege = privilege_map[privilege]
    return (get_privilege_flags(user, page_name) & privilege) != 0


def require_privilege(privilege):
    """
    Helper action decorator that checks if the currently logged in
    user does have the privilege required to perform that action.
    """
    def decorate(f):
        def oncall(request, name):
            if has_privilege(request.user, name, privilege):
                return f(request, name)
            if not request.user.is_authenticated():
                url = href('portal', 'login', next='http://%s%s' % (
                    request.get_host(),
                    request.path
                ))
                return HttpResponseRedirect(url)
            return AccessDeniedResponse()
        oncall.__name__ = f.__name__
        oncall.__module__ = f.__module__
        oncall.__doc__ = f.__doc__
        return oncall
    return decorate


def test_changes_allowed(user, page_name, old_text, new_text):
    """
    This method returns `True` if the user is allowed to change the text of
    a page from `old_text` to `new_text`. At the moment this just checks for
    changed metadata, in the future however it makes sense to also check for
    banned words here.
    """
    if has_privilege(user, page_name, PRIV_MANAGE):
        return True
    from inyoka.wiki.parser import parse
    from inyoka.wiki.parser.nodes import MetaData

    old = set()
    new = set()
    for text, metadata in (old_text, old), (new_text, new):
        tree = parse(text)
        for node in tree.query.by_type(MetaData):
            if node.key.startswith('X-') and \
               node.key not in LENIENT_METADATA_KEYS:
                for value in node.values:
                    metadata.add((node.key, value))
    return old == new
