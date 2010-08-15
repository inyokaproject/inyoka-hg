# -*- coding: utf-8 -*-
"""
    inyoka.pastebin.urls
    ~~~~~~~~~~~~~~~~~~~~

    The urls for the pastebin service.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from django.conf.urls.defaults import patterns

urlpatterns = patterns('inyoka.pastebin.views',
    (r'^$', 'index'),
    (r'^(\d+)/$', 'display'),
    (r'^raw/(\d+)/$', 'raw'),
    (r'^browse/$', 'browse'),
)


handler404 = 'inyoka.portal.views.not_found'
