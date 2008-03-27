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
from inyoka.ikhaya.models import Article, Category


legacy = LegacyDispatcher()
test_legacy_url = legacy.tester


@legacy.url('^/(\d{,3})/?$') # /\d{4} is reserved for year indexes
def article(args, match, article_id):
    try:
        article = Article.objects.get(article_id)
    except Article.DoesNotExist:
        return
    return href('ikhaya', article.slug)


@legacy.url('^/archive/(\d+)/(\d+)/?$')
def archive(args, match, year, month):
    return href('ikhaya', year, month)


@legacy.url('^/category/(\d+)/?$')
def category(args, match, category_id)
    try:
        category = Category.objects.get(category_id)
    except Category.DoesNotExist:
        return
    return href('ikhaya', category.slug)

