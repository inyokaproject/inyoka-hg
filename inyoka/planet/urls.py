# -*- coding: utf-8 -*-
"""
    inyoka.planet.urls
    ~~~~~~~~~~~~~~~~~~

    URL list for the planet.

    :copyright: 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from django.conf.urls.defaults import patterns


urlpatterns = patterns('inyoka.planet.views',
    (r'^$', 'index'),
    (r'^(\d+)/$', 'index'),
    (r'^suggest/$', 'suggest'),
    (r'^feeds/(?P<mode>[a-z]+)/(?P<count>\d+)/$', 'feed')
)


handler404 = 'inyoka.planet.views.not_found'
