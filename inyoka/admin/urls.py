#-*- coding: utf-8 -*-
"""
    inyoka.admin.urls
    ~~~~~~~~~~~~~~~~~

    The Admin views.

    :copyright: 2008 by Christopher Grebs, Benjamin Wiegand.
    :license: GNU GPL
"""
from django.conf.urls.defaults import patterns


urlpatterns = patterns('inyoka.admin.views',
    (r'^$', 'index'),
    (r'^config/$', 'config'),
    (r'^pages/$', 'pages'),
    (r'^pages/new/$', 'pages_edit'),
    (r'^pages/edit/(?P<page>.+)/$', 'pages_edit'),
    (r'^pages/delete/(?P<page_key>.+)/$', 'pages_delete'),
    (r'^planet/$', 'planet'),
    (r'^planet/new/$', 'planet_edit'),
    (r'^planet/edit/(?P<blog>.+)/$', 'planet_edit'),
    (r'^ikhaya/$', 'ikhaya'),
    (r'^ikhaya/articles/$', 'ikhaya_articles'),
    (r'^ikhaya/articles/(?P<page>\d)/$', 'ikhaya_articles'),
    (r'^ikhaya/articles/new/$', 'ikhaya_article_edit'),
    (r'^ikhaya/articles/new/(?P<suggestion_id>\d+)/$', 'ikhaya_article_edit'),
    (r'^ikhaya/articles/edit/(?P<article>.+)/$', 'ikhaya_article_edit'),
    (r'^ikhaya/articles/delete/(?P<article>.+)/$', 'ikhaya_article_delete'),
    (r'^ikhaya/categories/$', 'ikhaya_categories'),
    (r'^ikhaya/categories/new/$', 'ikhaya_category_edit'),
    (r'^ikhaya/categories/edit/(?P<category>.+)/$', 'ikhaya_category_edit'),
    (r'^ikhaya/categories/delete/(?P<category>.+)/$', 'ikhaya_category_delete'),
    (r'^ikhaya/icons/$', 'ikhaya_icons'),
    (r'^ikhaya/icons/new/$', 'ikhaya_icon_edit'),
    (r'^ikhaya/icons/edit/(?P<icon>.+)/$', 'ikhaya_icon_edit'),
    (r'^ikhaya/icons/delete/(?P<icon>.+)/$', 'ikhaya_icon_delete'),
    (r'^forum/$', 'forums'),
    (r'^forum/new/$', 'forums_edit'),
    (r'^forum/edit/(?P<id>\d+)/$', 'forums_edit'),
    (r'^ikhaya/icons/delete/(?P<icon>.+)/$', 'ikhaya_icon_delete'),
    (r'^events/$', 'events'),
    (r'^events/all/$', 'events', {'show_all': True}),
    (r'^events/edit/(?P<id>\d+)/$', 'event_edit'),
    (r'^events/delete/(?P<id>\d+)/$', 'event_delete'),
    (r'^events/new/$', 'event_edit'),
    (r'^users/$', 'users'),
    (r'^users/edit/(?P<username>.*)/$', 'edit_user'),
    (r'^users/new/$', 'new_user'),
    (r'^groups/$', 'groups'),
    (r'^groups/edit/(?P<name>.*)/$', 'groups_edit'),
    (r'^groups/new/$', 'groups_edit'),

)

handler404 = 'inyoka.portal.views.not_found'
handler500 = 'inyoka.portal.views.internal_server_error'
