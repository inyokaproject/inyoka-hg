# -*- coding: utf-8 -*-
"""
    inyoka.portal.legacyurls
    ~~~~~~~~~~~~~~~~~~~~~~~

    Portal legacy URL support (including old legacy urls from UUv1).

    :copyright: Copyright 2008 by Marian Sigler.
    :license: GNU GPL.
"""
#from inyoka.forum.models import Forum, Topic
from inyoka.utils.urls import href
from inyoka.utils.legacyurls import LegacyDispatcher


legacy = LegacyDispatcher()
test_legacy_url = legacy.tester


@legacy.url(r'^/ikhaya/(.*)$')
def ikhaya(args, match, url):
    # further redirects are done in ikhaya.legacyurls
    return href('ikhaya', url, **args)


@legacy.url(r'^/rss/')
def feeds(args, match):
    # users shall select a new feed themselves
    return href('static', 'feeds_update.xml')


# Very old legacy URLs from UUv1, copied from UUv2.portal.redirect

@legacy.url(r'^/portal\.php$')
def v1_portal(args, match):
    return href()

@legacy.url(r'^/index\.php$')
def v1_forum_index(args, match):
    return href('forum')

@legacy.url(r'^/viewtopic\.php$')
def v1_forum_topic(args, match):
    if 't' in args:
        return href('forum', 'topic', args['t'])
    elif 'p' in args:
        return href('forum', 'post', args['p'])
    else:
        return href('forum')

@legacy.url(r'^/viewforum\.php$')
def v1_forum_forum(args, match):
    if 'f' in args:
        return href('forum', 'forum', args['f'], args.get('start'))
    else:
        return href('forum')

@legacy.url(r'^/login\.php$')
def v1_login(args, match):
    return href('portal', 'login')

@legacy.url(r'^/map\.php$')
def v1_map(args, match):
    return href('portal', 'map')

@legacy.url(r'^/profile\.php$')
def v1_profile(args, match):
    return href('portal', 'usercp')

@legacy.url(r'^/wiki/(.+)$')
def v1_wiki(args, match, page):
    return href('wiki', page)
