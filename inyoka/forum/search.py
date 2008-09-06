# -*- coding: utf-8 -*-
"""
    inyoka.forum.search
    ~~~~~~~~~~~~~~~~~~~

    Search interfaces for the forum.

    :copyright: Copyright 2008 by Christoph Hack.
    :license: GNU GPL, see LICENSE for more details.
"""
from sqlalchemy.orm import eagerload
from inyoka.forum.acl import get_privileges, check_privilege
from inyoka.forum.models import Post, Forum
from inyoka.utils.urls import url_for
from inyoka.utils.html import striptags
from inyoka.utils.search import search, SearchAdapter
from inyoka.utils.decorators import deferred


class ForumSearchAuthDecider(object):
    """Decides whether a user can display a search result or not."""

    def __init__(self, user):
        self.user = user

    @deferred
    def privs(self):
        # the privileges are set on first call and not on init because this
        # would create one useless query if the user e.g. just searched the
        # wiki.
        privs = get_privileges(self.user, [f.id for f in Forum.query.all()])
        return dict((id, check_privilege(priv, 'read'))
            for id, priv in privs.iteritems())

    def __call__(self, auth):
        # TODO: Hide hidden topics
        return self.privs.get(auth[0], False)


class ForumSearchAdapter(SearchAdapter):
    type_id = 'f'
    auth_decider = ForumSearchAuthDecider

    def store(self, post_id):
        post = Post.query.options(eagerload('topic'), eagerload('author')) \
            .get(post_id)
        if post and post.topic:
            search.store(
                component='f',
                uid=post.id,
                title=post.topic.title,
                user=post.author_id,
                date=post.pub_date,
                collapse=post.topic_id,
                category=[p.slug for p in post.topic.forum.parents] + \
                    [post.topic.forum.slug],
                auth=[post.topic.forum_id, post.topic.hidden],
                text=post.text
            )

    def recv(self, post_id):
        post = Post.query.options(eagerload('topic'), eagerload('author')). \
            get(post_id)
        if post is None:
            return
        return {
            'title': post.topic.title,
            'user': post.author,
            'date': post.pub_date,
            'url': url_for(post),
            'component': u'Forum',
            'group': post.topic.forum.name,
            'group_url': url_for(post.topic.forum),
            'highlight': True,
            'text': striptags(post.rendered_text)
        }
search.register(ForumSearchAdapter())
