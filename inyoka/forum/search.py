# -*- coding: utf-8 -*-
"""
    inyoka.forum.search
    ~~~~~~~~~~~~~~~~~~~

    Search interfaces for the forum.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from inyoka.forum.acl import get_privileges, check_privilege
from inyoka.forum.models import Post, Forum, Topic
from inyoka.utils.urls import url_for, href
from inyoka.utils.search import search, SearchAdapter
from inyoka.utils.decorators import deferred
from inyoka.utils.database import db


class ForumSearchAuthDecider(object):
    """Decides whether a user can display a search result or not."""

    def __init__(self, user):
        self.user = user

    @deferred
    def privs(self):
        # the privileges are set on first call and not on init because this
        # would create one useless query if the user e.g. just searched the
        # wiki.
        privs = get_privileges(self.user, [f.id for f in Forum.query.get_cached()])
        return dict((id, check_privilege(priv, 'read'))
            for id, priv in privs.iteritems())

    def __call__(self, auth):
        # TODO: Hide hidden topics
        return self.privs.get(auth[0], False)


class ForumSearchAdapter(SearchAdapter):
    type_id = 'f'
    auth_decider = ForumSearchAuthDecider
    support_multi = True

    def store(self, post_id):
        post = Post.query.options(db.eagerload('topic'), db.eagerload('author'))
        post = post.get(post_id)
        if post is None:
            return
        self._store_post(post)

    def _store_post(self, post):
        try:
            forum = post.topic.cached_forum()
            search.store(
                component='f',
                uid=post.id,
                title=post.topic.title,
                user=post.author_id,
                date=post.pub_date,
                collapse=post.topic_id,
                category=[p.slug for p in forum.parents] + \
                    [forum.slug],
                auth=[post.topic.forum_id, post.topic.hidden],
                text=post.text,
                solved='1' if post.topic.solved else '0',
                version=post.topic.get_version_info(default=None),
            )
        except AttributeError:
            pass

    def store_multi(self, post_ids):
        range = 500
        i = 0
        post_ids = list(post_ids)
        max = len(post_ids)
        while i <= max:
            try:
                ids = post_ids[i:i+range]
            except IndexError:
                ids = post_ids[i:]
            if not ids:
                break
            posts = Post.query.options(db.eagerload('topic'), db.eagerload('author')) \
                              .filter(Post.id.in_(ids)).all()
            for post in posts:
                self._store_post(post)
            # cleanup some stuff
            search.flush()
            db.session.commit()
            # count up the index
            i += range

    def extract_data(self, post):
        return {'title': post.topic.title,
                'user': post.author.username,
                'date': post.pub_date,
                'url': href('forum', 'post', post.id),
                'component': u'Forum',
                'group': post.topic.cached_forum().name,
                'group_url': url_for(post.topic.cached_forum()),
                'highlight': True,
                'text': post.get_text(),
                'solved': post.topic.solved,
                'version': post.topic.get_version_info(False),
                'hidden': post.hidden or post.topic.hidden,
                'last_post_url': href('forum', 'post', post.topic.last_post_id),
                'user_url': url_for(post.author)}

    def recv(self, post_id):
        post = Post.query.options(db.eagerload('topic'), db.eagerload('author'))
        post = post.get(post_id)
        if post is None or post.topic is None:
            return
        return self.extract_data(post)

    def recv_multi(self, post_ids):
        posts = Post.query.options(db.eagerload('topic'), db.eagerload('author')) \
                    .filter(Post.id.in_(post_ids)).all()
        return [self.extract_data(post) for post in posts if post and post.topic]

    def get_doc_ids(self):
        pids = db.session.query(Post.id).filter(Post.topic_id==Topic.id)
        for pid in pids:
            yield pid.id


search.register(ForumSearchAdapter())
