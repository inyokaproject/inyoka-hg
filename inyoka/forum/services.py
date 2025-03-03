# -*- coding: utf-8 -*-
"""
    inyoka.forum.services
    ~~~~~~~~~~~~~~~~~~~~~

    Forum specific services.


    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from sqlalchemy.orm import eagerload
from django.db import transaction

from inyoka.forum.models import UBUNTU_VERSIONS, Topic, Post, Forum
from inyoka.forum.acl import get_forum_privileges, check_privilege, \
    have_privilege
from inyoka.portal.models import Subscription
from inyoka.portal.utils import abort_access_denied
from inyoka.utils.http import HttpResponse
from inyoka.utils.services import SimpleDispatcher
from inyoka.utils.templating import render_template
from inyoka.utils.database import session


def on_get_topic_autocompletion(request):
    qs = list(Topic.query.filter(Topic.slug.startswith(
                                  request.GET.get('q', '')))[:11])
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
    for id in request.GET.getlist('hidden[]'):
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
def subscription_action(request, action=None):
    assert action is not None and action in ('subscribe', 'unsubscribe')
    type = request.POST['type']
    slug = request.POST['slug']
    cls = None

    if type == 'forum':
        cls = Forum
    elif type == 'topic':
        cls = Topic

    col = str((type in ('forum', 'topic') and type+'_id' or type))

    obj = cls.query.filter(cls.slug==slug).one()
    if request.user.is_anonymous \
       or not have_privilege(request.user, obj, 'read'):
        #XXX: we should raise here, because it's nearly impossible
        #     to cach that in JS.
        return abort_access_denied(request)
    try:
        subscription = Subscription.objects.get(user=request.user, **{col: obj.id})
    except Subscription.DoesNotExist:
        if action == 'subscribe':
            Subscription(user=request.user, **{col: obj.id}).save()
    else:
        if action == 'unsubscribe':
            subscription.delete()


def on_change_status(request, solved=None):
    topic = Topic.query.filter_by(slug=request.POST['slug']).first()
    if not topic:
        return
    elif request.user.is_anonymous \
         or not have_privilege(request.user, topic.forum, 'read'):
        return abort_access_denied(request)
    if solved is not None:
        topic.solved = solved
        # reindex the whole topic to push the new read status to all
        # posts.
        topic.reindex()
        session.commit()


def on_get_version_details(request):
    version = request.GET['version']
    obj = [x for x in UBUNTU_VERSIONS if x.number == version][0]
    return {
        'number': obj.number,
        'codename': obj.codename,
        'lts': obj.lts,
        'active': obj.active,
        'class_': obj.class_,
        'current': obj.current,
        'link': obj.link
    }

def on_get_new_latest_posts(request):
    post = int(request.POST['post'])
    post = Post.query.get(post)

    posts = Post.query.filter(
        (Post.id > post.id) &
        (Post.topic_id == post.topic_id)
    ).order_by(Post.id.desc()).all()

    code = render_template('forum/_edit_latestpost_row.html', {
        '__main__': True,
        'posts': posts,
    })

    return HttpResponse(code)


dispatcher = SimpleDispatcher(
    get_topic_autocompletion=on_get_topic_autocompletion,
    get_post=on_get_post,
    toggle_categories=on_toggle_categories,
    subscribe=lambda r: subscription_action(r, 'subscribe'),
    unsubscribe=lambda r: subscription_action(r, 'unsubscribe'),
    mark_solved=lambda r: on_change_status(r, True),
    mark_unsolved=lambda r: on_change_status(r, False),
    get_version_details=on_get_version_details,
    get_new_latest_posts=on_get_new_latest_posts,
)
