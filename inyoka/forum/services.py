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


def on_toggle_categories(request):
    if request.user.is_anonymous:
        return False
    hidden_categories = set()
    for id in request.GET.getlist('hidden'):
        try:
            hidden_categories.add(int(id))
        except ValueError:
            pass
    request.user.settings['hidden_forum_categories'] = hidden_categories
    print hidden_categories
    request.user.save()
    return True


dispatcher = SimpleDispatcher(
    get_topic_autocompletion=on_get_topic_autocompletion,
    toggle_categories=on_toggle_categories
)
