# -*- coding: utf-8 -*-
"""
    inyoka.utils.cache
    ~~~~~~~~~~~~~~~~~~

    Holds the current active cache object.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from werkzeug.contrib.cache import MemcachedCache, SimpleCache
from inyoka.conf import settings


cache = (type('UnconfiguredCache', (object,), {}))()


def _set_cache(obj):
    cache.__class__ = obj.__class__
    cache.__dict__ = obj.__dict__


def set_real_cache():
    """Set the cache according to the settings."""
    if settings.MEMCACHE_SERVERS:
        from inyoka.utils.local import local
        _set_cache(MemcachedCache(settings.MEMCACHE_SERVERS, local=local))
    else:
        _set_cache(SimpleCache())


def set_test_cache():
    """Enable a simple cache for unittests."""
    _set_cache(SimpleCache())


# enable the real cache by default
set_real_cache()
