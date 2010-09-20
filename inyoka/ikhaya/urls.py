# -*- coding: utf-8 -*-
"""
    inyoka.ikhaya.urls
    ~~~~~~~~~~~~~~~~~~

    URL list for ikhaya.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from django.conf.urls.defaults import patterns


urlpatterns = patterns('inyoka.ikhaya.views',
    (r'^$', 'index'),
    (r'^(?P<page>\d+)/$', 'index'),
    (r'^(?P<year>\d+)/(?P<month>\d+)/$', 'index'),
    (r'^(?P<year>\d+)/(?P<month>\d+)/(?P<page>\d+)/$', 'index'),
    (r'^category/(?P<category_slug>[^/]+)/$', 'index'),
    (r'^category/(?P<category_slug>[^/]+)/(?P<page>\d+)/$', 'index'),
    (r'^archive/$', 'archive'),
    (r'^suggest/$', 'suggest'),
    (r'^newevent/$', 'event_new'),
    (r'^suggestions/$', 'suggestionlist'),
    (r'^suggestions/assign/(?P<suggestion>\d+)/(?P<username>[^/]+)/$', 'suggestion_assign_to'),
    (r'^suggestions/delete/(?P<suggestion>\d+)/$', 'suggestion_delete'),
    # XXX: This is a possible conflict with the url of the article feed
    (r'^feeds/comments/(?P<mode>\w+)/(?P<count>\d+)/$', 'comment_feed', {'id': None}),
    (r'^feeds/comments/(?P<id>\d+)/(?P<mode>\w+)/(?P<count>\d+)/$', 'comment_feed'),
    (r'^feeds/(?P<mode>\w+)/(?P<count>\d+)/$', 'article_feed', {'slug': None}),
    (r'^feeds/(?P<slug>[^/]+)/(?P<mode>\w+)/(?P<count>\d+)/$', 'article_feed'),
    (r'^(?P<year>\d+)/(?P<month>\d+)/(?P<day>\d+)/(?P<slug>[^/]+)/$', 'detail'),
    (r'^comment/(?P<comment_id>\d+)/hide/$', 'hide_comment'),
    (r'^comment/(?P<comment_id>\d+)/restore/$', 'restore_comment'),
    (r'^comment/(?P<comment_id>\d+)/edit/$', 'edit_comment'),
)


handler404 = 'inyoka.ikhaya.views.not_found'
