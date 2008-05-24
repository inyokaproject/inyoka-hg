# -*- coding: utf-8 -*-
"""
    inyoka.ikhaya.urls
    ~~~~~~~~~~~~~~~~~~

    URL list for ikhaya.

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL.
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
    (r'^suggestions/$', 'suggestionlist'),
    (r'^suggestions/assign/(?P<suggestion>\d+)/(?P<username>[^/]+)/$', 'suggestion_assign_to'),
    (r'^feeds/(?P<mode>\w+)/(?P<count>\d+)/$', 'feed'),
    (r'^feeds/(?P<category_slug>[^/]+)/(?P<mode>\w+)/(?P<count>\d+)/$','feed'),
    (r'^(?P<slug>.+)/$', 'detail'),

)


handler404 = 'inyoka.ikhaya.views.not_found'
