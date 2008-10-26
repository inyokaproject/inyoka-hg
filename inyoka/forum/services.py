# -*- coding: utf-8 -*-
"""
    inyoka.forum.services
    ~~~~~~~~~~~~~~~~~~~~~

    Forum specific services.


    :copyright: Copyright 2008 by Armin Ronacher, Benjamin Wiegand.
    :license: GNU GPL.
"""
from sqlalchemy.orm import eagerload
from django.db import transaction
from inyoka.forum.models import Topic, Post, Forum
from inyoka.forum.acl import get_forum_privileges, check_privilege, \
    have_privilege
from inyoka.portal.models import Subscription
from inyoka.utils.services import SimpleDispatcher


def on_get_topic_autocompletion(request):
    qs = list(Topic.objects.filter(slug__startswith=
                                  request.GET.get('q', ''))[:11])
    if len(qs) > 10:
        qs[10] = '...'
    return [x.slug for x in qs]


def on_get_post(request):
    try:
        post = Post.query.options(eagerload('topic'), eagerload('author')) \
                         .get(int(request.GET['post_id']))
    except (KeyError, ValueError):
        return None
    if not post:
        return None
    privs = get_forum_privileges(request.user, post.topic.forum_id)
    if not check_privilege(privs, 'read') or (not check_privilege(privs,
                       'moderate') and post.topic.hidden or post.hidden):
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

@transaction.autocommit
def on_subscribe(request):
    type = request.POST['type']
    slug = request.POST['slug']
    obj = None

    if type == 'forum':
        obj = Forum
    elif type == 'topic':
        obj = Topic

    col = str((type in ('forum', 'topic') and type+'_id' or type))

    x = obj.query.filter(obj.slug==slug).one()
    if not have_privilege(request.user, x, 'read'):
        #XXX: we should raise here, because it's nearly impossible
        #     to cach that in JS.
        return abort_access_denied(request)
    try:
        s = Subscription.objects.get(user=request.user, **{col: x.id})
    except Subscription.DoesNotExist:
        Subscription(user=request.user, **{col: x.id}).save()


@transaction.autocommit
def on_unsubscribe(request):
    type = request.POST['type']
    slug = request.POST['slug']
    obj = None

    if type == 'forum':
        obj = Forum
    elif type == 'topic':
        obj = Topic

    col = str((type in ('forum', 'topic') and type+'_id' or type))

    x = obj.query.filter(obj.slug==slug).one()
    if not have_privilege(request.user, x, 'read'):
        #XXX: we should raise here, because it's nearly impossible
        #     to catch that in JS.
        return abort_access_denied(request)
    try:
        s = Subscription.objects.get(user=request.user, **{col: x.id})
    except Subscription.DoesNotExist:
        pass
    else:
        # there's already a subscription for this forum, remove it
        s.delete()


dispatcher = SimpleDispatcher(
    get_topic_autocompletion=on_get_topic_autocompletion,
    get_post=on_get_post,
    toggle_categories=on_toggle_categories,
    subscribe=on_subscribe,
    unsubscribe=on_unsubscribe
)
