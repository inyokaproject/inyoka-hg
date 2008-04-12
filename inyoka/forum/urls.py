# -*- coding: utf-8 -*-
"""
    inyoka.forum.urls
    ~~~~~~~~~~~~~~~~~

    URL list for the forum.

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL.
"""
from django.conf.urls.defaults import patterns


urlpatterns = patterns('inyoka.forum.views',
    (r'^$', 'index'),
    (r'^topic/(?P<topic_slug>[^/]+)/$', 'viewtopic'),
    (r'^topic/(?P<topic_slug>[^/]+)/(?P<page>\d+)/$', 'viewtopic'),
    (r'^topic/(?P<topic_slug>[^/]+)/reply/$', 'edit'),
    (r'^topic/(?P<topic_slug>[^/]+)/delete/$', 'delete_topic'),
    (r'^topic/(?P<topic_slug>[^/]+)/hide/$', 'hide_topic'),
    (r'^topic/(?P<topic_slug>[^/]+)/restore/$', 'restore_topic'),
    (r'^topic/(?P<topic_slug>[^/]+)/split/$', 'splittopic'),
    (r'^topic/(?P<topic_slug>[^/]+)/move/$', 'movetopic'),
    (r'^topic/(?P<topic_slug>[^/]+)/solve/$', 'change_status',
                                    {'solved': True}),
    (r'^topic/(?P<topic_slug>[^/]+)/unsolve/$', 'change_status',
                                    {'solved': False}),
    (r'^topic/(?P<topic_slug>[^/]+)/lock/$', 'change_status',
                                    {'locked': True}),
    (r'^topic/(?P<topic_slug>[^/]+)/unlock/$', 'change_status',
                                    {'locked': False}),
    (r'^topic/(?P<topic_slug>[^/]+)/report/$', 'report'),
    (r'^topic/(?P<topic_slug>[^/]+)/report_done/$', 'report',
                                    {'status': 'done'}),
    (r'^topic/(?P<topic_slug>[^/]+)/subscribe', 'subscribe_topic'),
    (r'^topic/(?P<topic_slug>[^/]+)/unsubscribe', 'unsubscribe_topic'),
    (r'^reported_topics/$', 'reportlist'),
    (r'^post/(?P<post_id>\d+)/$', 'post'),
    (r'^post/(?P<post_id>\d+)/edit/$', 'edit'),
    (r'^post/(?P<quote_id>\d+)/quote/$', 'edit'),
    (r'^post/(?P<post_id>\d+)/hide/$', 'hide_post'),
    (r'^post/(?P<post_id>\d+)/restore/$', 'restore_post'),
    (r'^post/(?P<post_id>\d+)/delete/$', 'delete_post'),
    (r'^forum/(?P<slug>[^/]+)/$', 'forum'),
    (r'^forum/(?P<slug>[^/]+)/subscribe/$', 'subscribe_forum'),
    (r'^forum/(?P<slug>[^/]+)/unsubscribe/$', 'unsubscribe_forum'),
    (r'^forum/(?P<slug>[^/]+)/(?P<page>\d+)/$', 'forum'),
    (r'^forum/(?P<forum_slug>[^/]+)/newtopic/$', 'edit'),
    (r'^feeds/(?P<mode>[a-z]+)/(?P<count>\d+)/$', 'feed'),
    (r'^feeds/(?P<component>forum|topic)/(?P<slug>[^/]+)/'
     r'(?P<mode>[a-z]+)/(?P<count>\d+)/$', 'feed'),
    (r'^category/(?P<category>[^/]+)/$', 'index'),
    (r'^new_discussion/(?P<article>.+)/$', 'newtopic'),
    (r'^markread/$', 'markread'),
    (r'^category/(?P<slug>[^/]+)/markread/$', 'markread'),
    (r'^forum/(?P<slug>[^/]+)/markread/$', 'markread'),
    (r'^newposts/$', 'newposts'),
    (r'^newposts/(?P<page>\d+)/$', 'newposts'),
    (r'^category/(?P<slug>[^/]+)/welcome/$', 'welcome'),
    (r'^forum/(?P<slug>[^/]+)/welcome/$', 'welcome')
)


handler404 = 'inyoka.forum.views.not_found'
