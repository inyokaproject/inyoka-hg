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
    (r'^markup.css', 'markup_styles'),
    (r'^login/$', 'login'),
    (r'^logout/$', 'logout'),
    (r'^search/$', 'search'),
    (r'^users/$', 'memberlist'),
    (r'^users/(?P<page>\d+)/$', 'memberlist'),
    (r'^user/(?P<username>.+)/$', 'profile'),
    (r'^groups/$', 'grouplist'),
    (r'^groups/(?P<page>\d+)/$', 'grouplist'),
    (r'^group/(?P<name>[^/]+)/$', 'group'),
    (r'^group/(?P<name>[^/]+)/(?P<page>\d+)/$', 'group'),
    (r'^usercp/$', 'usercp'),
    (r'^usercp/settings/$', 'usercp_settings'),
    (r'^usercp/profile/$', 'usercp_profile'),
    (r'^usercp/password/$', 'usercp_password'),
    (r'^usercp/subscriptions/$', 'usercp_subscriptions'),
    (r'^usercp/subscriptions/notified/$', 'usercp_subscriptions', {'notified_only': True}),
    (r'^usercp/subscriptions/(?P<page>\d+)/$', 'usercp_subscriptions'),
    (r'^usercp/subscriptions/notified/(?P<page>\d+)/$', 'usercp_subscriptions', {'notified_only': True}),
    (r'^usercp/deactivate/$', 'usercp_deactivate'),
    (r'^usercp/userpage/$', 'usercp_userpage'),
    (r'^privmsg/$', 'privmsg'),
    (r'^privmsg/new/$', 'privmsg_new'),
    (r'^privmsg/new/(?P<username>.+)/$', 'privmsg_new'),
    (r'^privmsg/(?P<folder>[a-z]+)/$', 'privmsg'),
    (r'^privmsg/(?P<folder>[a-z]+)/page/$', 'privmsg'),
    (r'^privmsg/(?P<folder>[a-z]+)/page/(?P<page>\d+)/$', 'privmsg'),
    (r'^privmsg/(?P<entry_id>\d+)/$', 'privmsg'),
    (r'^privmsg/(?P<folder>[a-z]+)/(?P<entry_id>\d+)/$', 'privmsg'),
    (r'^map/$', 'usermap'),
    (r'^whoisonline/$', 'whoisonline'),
    (r'^inyoka/$', 'about_inyoka'),
    (r'^register/$', 'register'),
    (r'^(?P<action>activate|delete)/(?P<username>[^/]+)/'
     r'(?P<activation_key>.*?)/$', 'activate'),
    (r'^register/resend/(?P<username>[^/]+)/$', 'resend_activation_mail'),
    (r'^lost_password/$', 'lost_password'),
    (r'^lost_password/(?P<username>[^/]+)/(?P<new_password_key>[a-z0-9]+)/$', 'set_new_password'),
    (r'^confirm/$', 'confirm'),
    (r'^confirm/(?P<action>[^/]+)/$', 'confirm'),
    (r'^usercp/reactivate/$', 'confirm', {'action':'reactivate_user'}),
    # ^ legacy support, can be removed after september 15th
    (r'^feeds/$', 'feedselector'),
    (r'^feeds/(?P<app>[^/]+)/$', 'feedselector'),
    (r'^calendar/$', 'calendar_overview'),
    (r'^calendar/(?P<year>\d{4})/(?P<month>(0?\d|1[0-2]))/$', 'calendar_month'),
    (r'^calendar/(?P<slug>.*?)/$', 'calendar_detail'),
    (r'^opensearch/(?P<app>[a-z]+)/$', 'open_search'),
    # static pages
    (r'^([-A-Za-z_]+)/$', 'static_page')
)


handler404 = 'inyoka.portal.views.not_found'
handler500 = 'inyoka.portal.views.internal_server_error'
