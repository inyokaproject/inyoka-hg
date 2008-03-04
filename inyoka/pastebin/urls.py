# -*- coding: utf-8 -*-
"""
    inyoka.pastebin.urls
    ~~~~~~~~~~~~~~~~~~~~

    The urls for the pastebin service.

    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from django.conf.urls.defaults import patterns

urlpatterns = patterns('inyoka.pastebin.views',
    (r'^$', 'index'),
    (r'^(\d+)/$', 'display'),
    (r'^raw/(\d+)/$', 'raw'),
    (r'^browse/$', 'browse'),
    (r'^browse/(?P<page>\d+)/$', 'browse')
)


handler404 = 'inyoka.portal.views.not_found'
