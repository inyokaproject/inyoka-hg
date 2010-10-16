# -*- coding: utf-8 -*-
"""
    inyoka.utils.cache
    ~~~~~~~~~~~~~~~~~~

    Holds the current active cache object.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from werkzeug.contrib.cache import MemcachedCache, SimpleCache, _test_memcached_key
from inyoka.utils.local import current_request
from inyoka.utils.debug import find_calling_context

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
            servers.set_behaviors({'tcp_nodelay': True, 'no_block': True})
        else:
            servers = settings.MEMCACHE_SERVERS
        _set_cache(MemcachedCache(servers, key_prefix=settings.CACHE_PREFIX))
    else:
        _set_cache(SimpleCache())
    if settings.DEBUG:
        global cache
        cache = CacheDebugProxy(cache)


def set_test_cache():
    """Enable a simple cache for unittests."""
    _set_cache(SimpleCache())


class CacheDebugProxy(object):
    """A proxy for a werkzeug.contrib.Cache which logs all queries for
    debugging purposes."""


    def _log(self, query, result):
        request = current_request._get_current_object()
        if not hasattr(request, 'cache_queries'):
            request.cache_queries = list()
        ctx = find_calling_context(3)
        request.cache_queries.append((ctx, query, result))
        return result

    def __init__(self, cache):
        self.cache = cache

    def add(self, key, value, timeout=None):
        return self._log('ADD %r %r (%r)' % (key, value, timeout),
            self.cache.add(key, value, timeout))

    def clear(self):
        return self._log('CLEAR',
            self.cache.clear())

    def dec(self, key, delta=1):
        return self._log('DEC %r %r' % (key, delta),
            self.cache.dec(key, delta))

    def delete(self, key):
        return self._log('DELETE %r' % key,
            self.cache.delete(key))

    def delete_many(self, *keys):
        return self._log('DELETE MANY %r' % (keys,),
            self.cache.delete_many(*keys))

    def get(self, key):
        return self._log('GET %r' % key,
            self.cache.get(key))

    def get_dict(self, *keys):
        return self._log('GET DICT %r' % (keys,),
            self.cache.get_dict(*keys))

    def get_many(self, *keys):
        return self._log('GET MANY %r' % (keys,),
            self.cache.get_many(*keys))

    def inc(self, key, delta=1):
        return self._log('INC %r %r' % (key, delta),
            self.cache.inc(key, delta))

    def set(self, key, value, timeout=None):
        return self._log('SET %r %r (%r)' % (key, value, timeout),
            self.cache.set(key, value, timeout))

    def set_many(self, mapping, timeout=None):
        return self._log('SET MANY %r (%r)' % (mapping, timeout),
            self.cache.set_many(mapping, timeout))

# enable the real cache by default
set_real_cache()
