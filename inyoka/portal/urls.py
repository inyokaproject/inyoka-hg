# -*- coding: utf-8 -*-
"""
    inyoka.portal.urls
    ~~~~~~~~~~~~~~~~~~

    The urls for the main portal (index page, error pages, login page etc.)

    :copyright: Copyright 2007 by Armin Ronacher
    :license: GNU GPL.
"""
from django.conf.urls.defaults import patterns


urlpatterns = patterns('inyoka.portal.views',
    (r'^$', 'index'),
    (r'^login/$', 'login'),
    (r'^logout/$', 'logout'),
    (r'^search/$', 'search'),
    (r'^users/$', 'memberlist'),
    # XXX: This may conflict with usernames that contain only digits
    (r'^users/(?P<page>\d+)/$', 'memberlist'),
    (r'^users/(?P<username>[^/]+)/$', 'profile'),
    (r'^groups/$', 'grouplist'),
    (r'^groups/(?P<name>[^/]+)/$', 'group'),
    (r'^groups/(?P<name>[^/]+)/(?P<page>\d+)/$', 'group'),
    (r'^usercp/$', 'usercp'),
    (r'^usercp/settings/$', 'usercp_settings'),
    (r'^usercp/profile/$', 'usercp_profile'),
    (r'^usercp/password/$', 'usercp_password'),
    (r'^usercp/subscriptions/$', 'usercp_subscriptions'),
    (r'^usercp/deactivate/$', 'usercp_deactivate'),
    (r'^privmsg/$', 'privmsg'),
    (r'^privmsg/new/$', 'privmsg_new'),
    (r'^privmsg/new/(?P<username>[^/]+)/$', 'privmsg_new'),
    (r'^privmsg/(?P<folder>[a-z]+)/$', 'privmsg'),
    (r'^privmsg/(?P<folder>[a-z]+)/(?P<entry_id>\d+)/$', 'privmsg'),
    (r'^map/$', 'usermap'),
    (r'^whoisonline/$', 'whoisonline'),
    (r'^inyoka/$', 'about_inyoka'),
    (r'^register/$', 'register'),
    (r'^register/(?P<action>activate|delete)/(?P<username>.*?)/'
     r'(?P<activation_key>.*?)/$', 'activate'),
    (r'^register/resend/(?P<username>.*?)/$', 'resend_activation_mail'),
    (r'^lost_password/$', 'lost_password'),
    (r'^_captcha/$', 'get_captcha'),
    (r'^feeds/$', 'feedselector'),
    (r'^feeds/(?P<app>[^/]+)/$', 'feedselector'),
    (r'^calendar/$', 'calendar'),
    (r'^calendar/(?P<year>\d+)-(?P<month>\d+)/$', 'calendar'),
    # static pages
    (r'^([-A-Za-z_]+)/$', 'static_page'),
)


handler404 = 'inyoka.portal.views.not_found'
handler500 = 'inyoka.portal.views.internal_server_error'
