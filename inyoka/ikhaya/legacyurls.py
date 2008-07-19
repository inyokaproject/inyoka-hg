# -*- coding: utf-8 -*-
"""
    inyoka.ikhaya.legacyurls
    ~~~~~~~~~~~~~~~~~~~~~~~

    Ikhaya legacy URL support.

    :copyright: Copyright 2008 by Marian Sigler.
    :license: GNU GPL.
"""
#from inyoka.forum.models import Forum, Topic
from inyoka.utils.urls import href
from inyoka.utils.legacyurls import LegacyDispatcher
from inyoka.ikhaya.models import Category


legacy = LegacyDispatcher()
test_legacy_url = legacy.tester


@legacy.url('^/archive/(\d+)/(\d+)/?$')
def archive(args, match, year, month):
    return href('ikhaya', year, month)


@legacy.url('^/category/(\d+)/?$')
def category(args, match, category_id):
    try:
        category = Category.objects.filter(id=int(category_id))[0]
    except Category.DoesNotExist:
        return
    return href('ikhaya', 'category', category.slug)
