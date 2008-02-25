# -*- coding: utf-8 -*-
"""
    inyoka.forum.legacyurls
    ~~~~~~~~~~~~~~~~~~~~~~~

    Forum legacy URL support.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from inyoka.forum.models import Forum, Topic
from inyoka.utils.urls import href
from inyoka.utils.legacyurls import LegacyDispatcher


legacy = LegacyDispatcher()
test_legacy_url = legacy.tester


@legacy.url(r'^/viewforum\.php/?$')
@legacy.url(r'^/forum/(\d+)(?:/(\d+))?/?$')
@legacy.url(r'^/category/(\d+)/?$')
def get_old_forum_url(args, match, forum_id=None, offset=None):
    if forum_id is None:
        try:
            forum_id = int(args['f'])
        except (KeyError, ValueError):
            return
    try:
        forum = Forum.objects.get(id=forum_id)
    except Forum.DoesNotExist:
        return
    if offset is None:
        page = 1
    else:
        page = (offset / POSTS_PER_PAGE) + 1
    if page <= 1:
        return href('forum', 'forum', forum.slug)
    return href('forum', 'forum', forum.slug, page)


@legacy.url(r'^/viewtopic\.php/?$')
@legacy.url(r'^/topic/([0-9]+)(?:/([0-9]+))?/?$')
def get_old_topic_url(args, match, topic_id=None, offset=None):
    if topic_id is None:
        try:
            topic_id = int(args['t'])
        except (KeyError, ValueError):
            try:
                post_id = int(args['p'])
            except (KeyError, ValueError):
                return
            return href('forum', 'post', post_id)
    try:
        topic = Topic.objects.get(id=topic_id)
    except Topic.DoesNotExist:
        return
    if offset is None:
        page = 1
    else:
        page = (offset / POSTS_PER_PAGE) + 1
    if page <= 1:
        return href('forum', 'topic', topic.slug)
    return href('forum', 'topic', topic.slug, page)
