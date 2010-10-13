# -*- coding: utf-8 -*-
"""
    inyoka.utils.cache
    ~~~~~~~~~~~~~~~~~~

    Holds the current active cache object.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from werkzeug.contrib.cache import MemcachedCache, SimpleCache, _test_memcached_key
try:
    from pylibmc import Client
    _pylibmc_available = True
except ImportError:
    _pylibmc_available = False
from inyoka.conf import settings


cache = (type('UnconfiguredCache', (object,), {}))()


def _set_cache(obj):
    cache.__class__ = obj.__class__
    cache.__dict__ = obj.__dict__


def set_real_cache():
    """Set the cache according to the settings."""
    if settings.MEMCACHE_SERVERS:
        if _pylibmc_available:
            servers = Client(settings.MEMCACHE_SERVERS, binary=True)
        else:
            servers = settings.MEMCACHE_SERVERS
        _set_cache(MemcachedCache(servers, key_prefix=settings.CACHE_PREFIX))
    else:
        _set_cache(SimpleCache())


def set_test_cache():
    """Enable a simple cache for unittests."""
    _set_cache(SimpleCache())


# enable the real cache by default
set_real_cache()
