# -*- coding: utf-8 -*-
"""
    inyoka.utils.cache
    ~~~~~~~~~~~~~~~~~~

    Holds the current active cache object.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from werkzeug.contrib.cache import NullCache, MemcachedCache, SimpleCache
from django.conf import settings


cache = (type('UnconfiguredCache', (object,), {}))()


def _set_cache(obj):
    cache.__class__ = obj.__class__
    cache.__dict__ = obj.__dict__


def set_real_cache():
    """Set the cache according to the settings."""
    if settings.MEMCACHE_SERVERS:
        _set_cache(MemcachedCache(settings.MEMCACHE_SERVERS))
    else:
        _set_cache(NullCache())


def set_test_cache():
    """Enable a simple cache for unittests."""
    _set_cache(SimpleCache())


# enable the real cache by default
set_real_cache()
