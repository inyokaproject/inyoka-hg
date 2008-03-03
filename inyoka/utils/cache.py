# -*- coding: utf-8 -*-
"""
    inyoka.utils.cache
    ~~~~~~~~~~~~~~~~~~

    Holds the current active cache object.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from werkzeug.contrib.cache import NullCache, MemcachedCache
from django.conf import settings


if settings.MEMCACHE_SERVERS:
    cache = MemcachedCache(settings.MEMCACHE_SERVERS)
else:
    cache = NullCache()
