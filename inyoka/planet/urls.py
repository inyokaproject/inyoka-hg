# -*- coding: utf-8 -*-
"""
    inyoka.planet.urls
    ~~~~~~~~~~~~~~~~~~

    URL list for the planet.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from django.conf.urls.defaults import patterns


urlpatterns = patterns('inyoka.planet.views',
    (r'^$', 'index'),
    (r'^(\d+)/$', 'index'),
    (r'^hide/(?P<id>\d+)/$', 'hide_entry'),
    (r'^suggest/$', 'suggest'),
    (r'^feeds/(?P<mode>[a-z]+)/(?P<count>\d+)/$', 'feed'),
)


handler404 = 'inyoka.planet.views.not_found'
