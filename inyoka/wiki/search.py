# -*- coding: utf-8 -*-
"""
    inyoka.wiki.search
    ~~~~~~~~~~~~~~~~~~

    Search interfaces for the wiki.

    :copyright: Copyright 2008 by Christoph Hack.
    :license: GNU GPL, see LICENSE for more details.
"""
from inyoka.wiki.acl import MultiPrivilegeTest, PRIV_READ
from inyoka.wiki.models import Revision
from inyoka.utils.urls import url_for
from inyoka.utils.search import search, SearchAdapter


class WikiSearchAuthDecider(object):
    """Decides whetever a user can display a search result or not."""

    def __init__(self, user):
        self.test = MultiPrivilegeTest(user)

    def __call__(self, page_name):
        return self.test.has_privilege(page_name, PRIV_READ)


class WikiSearchAdapter(SearchAdapter):
    type_id = 'w'
    auth_decider = WikiSearchAuthDecider

    def recv(self, page_id):
        rev = Revision.objects.select_related(depth=1) \
                .filter(page__id=page_id).latest()
        return {
            'title': rev.page.name,
            'user': rev.user,
            'date': rev.change_date,
            'url': url_for(rev.page),
            'component': u'Wiki',
            'highlight': True
        }

    def store(self, page_id):
        rev = Revision.objects.select_related(depth=1) \
                .filter(page__id=page_id).latest()
        search.store(
            component='w',
            uid=rev.page.id,
            title=rev.page.name,
            user=rev.user_id,
            date=rev.change_date,
            auth=rev.page.name,
            text=rev.text.value
        )
search.register(WikiSearchAdapter())
