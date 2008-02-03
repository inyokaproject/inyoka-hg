# -*- coding: utf-8 -*-
"""
    inyoka.forum.services
    ~~~~~~~~~~~~~~~~~~~~~

    Forum specific services.


    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from inyoka.forum.models import Topic
from inyoka.utils.services import SimpleDispatcher


def on_get_topic_autocompletion(request):
    qs = list(Topic.objects.filter(slug__startswith=
                                  request.GET.get('q', ''))[:11])
    if len(qs) > 10:
        qs[10] = '...'
    return [x.slug for x in qs]


def on_toggle_category(request):
    if request.user.is_anonymous:
        return False
    try:
        category_id = int(request.args['id'])
    except (ValueError, KeyError):
        return False
    categories = request.user.settings.get('hidden_forum_categories', set())
    if request.args.get('hide', 'false'):
        categories.discard(category_id)
    else:
        categories.add(category_id)
    request.user.save()
    return True


dispatcher = SimpleDispatcher(
    get_topic_autocompletion=on_get_topic_autocompletion,
    toggle_category=on_toggle_category
)
