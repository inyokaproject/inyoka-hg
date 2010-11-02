# -*- coding: utf-8 -*-
"""
    inyoka.wiki.search
    ~~~~~~~~~~~~~~~~~~

    Search interfaces for the wiki.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from django.db import connection
from inyoka.wiki.acl import MultiPrivilegeTest, PRIV_READ
from inyoka.wiki.models import Revision
from inyoka.utils.urls import url_for, href
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

    def extract_data(self, rev):
        return {'title': rev.page.name,
                'user': rev.user.username,
                'date': rev.change_date,
                'url': url_for(rev.page),
                'component': u'Wiki',
                'group': u'Wiki',
                'group_url': href('wiki'),
                'highlight': True,
                'text': rev.rendered_text,
                'hidden': rev.deleted,
                'user_url': url_for(rev.user)}

    def recv(self, page_id):
        rev = Revision.objects.select_related(depth=2) \
                .filter(page__id=page_id).latest()
        return self.extract_data(rev)

    def recv_multi(self, page_ids):
        #TODO: make this efficient...
        return [self.recv(id) for id in page_ids]

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
            text=rev.text.value,
            category=rev.attachment_id and '__attachment__' or None
        )

    def get_doc_ids(self):
        cur = connection.cursor()
        cur.execute('SELECT id FROM wiki_page;')
        for row in cur.fetchall():
            yield row[0]
        cur.close()


search.register(WikiSearchAdapter())
