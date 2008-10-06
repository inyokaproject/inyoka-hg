# -*- coding: utf-8 -*-
"""
    inyoka.utils.cache
    ~~~~~~~~~~~~~~~~~~

    Holds the current active cache object.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from werkzeug.contrib.cache import MemcachedCache, SimpleCache, _test_memcached_key
from inyoka.conf import settings
from inyoka.utils.local import local


cache = (type('UnconfiguredCache', (object,), {}))()


class InyokaMemcachedCache(MemcachedCache):

    def __init__(self, servers, default_timeout=300, key_prefix=None):
        MemcachedCache.__init__(self, servers, default_timeout, key_prefix)

    def get(self, key):
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if self.key_prefix:
            key = self.key_prefix + key

        # memcached doesn't support keys longer than that.  Because often
        # checks for so long keys can occour because it's tested from user
        # submitted data etc we fail silently for getting.
        if _test_memcached_key(key):
            if not hasattr(local, 'cache'):
                local.cache = {}
            if key in local.cache:
                return local.cache.get(key)

            value = self._client.get(key)
            local.cache[key] = value
            return value

def _set_cache(obj):
    cache.__class__ = obj.__class__
    cache.__dict__ = obj.__dict__


def set_real_cache():
    """Set the cache according to the settings."""
    if settings.MEMCACHE_SERVERS:
        from inyoka.utils.local import local
        _set_cache(InyokaMemcachedCache(settings.MEMCACHE_SERVERS))
    else:
        _set_cache(SimpleCache())


def set_test_cache():
    """Enable a simple cache for unittests."""
    _set_cache(SimpleCache())


# enable the real cache by default
set_real_cache()
