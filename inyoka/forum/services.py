# -*- coding: utf-8 -*-
"""
    inyoka.forum.services
    ~~~~~~~~~~~~~~~~~~~~~

    Forum specific services.


    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from inyoka.forum.models import Topic, Post
from inyoka.forum.acl import get_forum_privileges
from inyoka.utils.services import SimpleDispatcher


def on_get_topic_autocompletion(request):
    qs = list(Topic.objects.filter(slug__startswith=
                                  request.GET.get('q', ''))[:11])
    if len(qs) > 10:
        qs[10] = '...'
    return [x.slug for x in qs]


def on_get_post(request):
    try:
        post = Post.objects.get(id=int(request.GET['post_id']))
    except (KeyError, ValueError, Post.DoesNotExist):
        return None
    privileges = get_forum_privileges(request.user, post.topic.forum)
    if not privileges['read'] or (not privileges['moderate'] and
       post.topic.hidden or post.hidden):
        return None
    return {
        'id':       post.id,
        'author':   post.author.username,
        'text':     post.text
    }


def on_toggle_categories(request):
    if request.user.is_anonymous:
        return False
    hidden_categories = set()
    for id in request.GET.getlist('hidden'):
        try:
            hidden_categories.add(int(id))
        except ValueError:
            pass
    if not hidden_categories:
        request.user.settings.pop('hidden_forum_categories', None)
    else:
        request.user.settings['hidden_forum_categories'] = hidden_categories
    request.user.save()
    return True


dispatcher = SimpleDispatcher(
    get_topic_autocompletion=on_get_topic_autocompletion,
    get_post=on_get_post,
    toggle_categories=on_toggle_categories
)
