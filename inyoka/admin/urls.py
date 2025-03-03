#-*- coding: utf-8 -*-
"""
    inyoka.admin.urls
    ~~~~~~~~~~~~~~~~~

    The Admin views.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
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
    (r'^ikhaya/articles/(?P<page>\d+)/$', 'ikhaya_articles'),
    (r'^ikhaya/articles/new/$', 'ikhaya_article_edit'),
    (r'^ikhaya/articles/new/(?P<suggestion_id>\d+)/$', 'ikhaya_article_edit'),
    (r'^ikhaya/articles/edit/(?P<article_id>\d+)/$', 'ikhaya_article_edit'),
    (r'^ikhaya/articles/delete/(?P<article_id>\d+)/$', 'ikhaya_article_delete'),
    (r'^ikhaya/categories/$', 'ikhaya_categories'),
    (r'^ikhaya/categories/new/$', 'ikhaya_category_edit'),
    (r'^ikhaya/categories/edit/(?P<category>.+)/$', 'ikhaya_category_edit'),
    (r'^ikhaya/categories/delete/(?P<category>.+)/$', 'ikhaya_category_delete'),
    (r'^files/$', 'files'),
    (r'^files/new/$', 'file_edit'),
    (r'^files/edit/(?P<file>.+)/$', 'file_edit'),
    (r'^files/delete/(?P<file>.+)/$', 'file_delete'),
    (r'^forum/$', 'forums'),
    (r'^forum/new/$', 'forum_edit'),
    (r'^forum/edit/(?P<slug>.+)/$', 'forum_edit'),
    (r'^events/$', 'events'),
    (r'^events/all/$', 'events', {'show_all': True}),
    (r'^events/invisible/$', 'events', {'invisible':True}),
    (r'^events/edit/(?P<id>\d+)/$', 'event_edit'),
    (r'^events/delete/(?P<id>\d+)/$', 'event_delete'),
    (r'^events/new/$', 'event_edit'),
    (r'^users/$', 'users'),
    (r'^users/edit/(?P<username>[^/]+)/$', 'user_edit'),
    (r'^users/edit/(?P<username>[^/]+)/profile/$', 'user_edit_profile'),
    (r'^users/edit/(?P<username>[^/]+)/settings/$', 'user_edit_settings'),
    (r'^users/edit/(?P<username>[^/]+)/groups/$', 'user_edit_groups'),
    (r'^users/edit/(?P<username>[^/]+)/privileges/$', 'user_edit_privileges'),
    (r'^users/edit/(?P<username>[^/]+)/password/$', 'user_edit_password'),
    (r'^users/edit/(?P<username>[^/]+)/status/$', 'user_edit_status'),
    (r'^users/new/$', 'user_new'),
    (r'^users/resend_activation_mail/$', 'resend_activation_mail'),
    (r'^users/mail/(?P<username>.*)/$', 'user_mail'),
    (r'^users/special_rights/$', 'users_with_special_rights'),
    (r'^groups/$', 'groups'),
    (r'^groups/edit/(?P<name>.*)/$', 'group_edit'),
    (r'^groups/new/$', 'group_edit'),
    (r'^styles/$', 'styles'),
)

handler404 = 'inyoka.admin.views.not_found'
