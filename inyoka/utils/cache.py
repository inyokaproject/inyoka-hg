# -*- coding: utf-8 -*-
"""
    inyoka.utils.cache
    ~~~~~~~~~~~~~~~~~~

    Holds the current active cache object.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from werkzeug.contrib.cache import MemcachedCache, SimpleCache, _test_memcached_key
from django.utils.encoding import force_unicode
from inyoka.utils.local import current_request, _request_cache, local_has_key
from inyoka.utils.debug import find_calling_context

try:
    from pylibmc import Client, NotFound
    _pylibmc_available = True
except ImportError:
    Client = type('Client', (object,), {})
    _pylibmc_available = False
from inyoka.conf import settings


cache = (type('UnconfiguredCache', (object,), {}))()
request_cache = None


def _set_cache(obj):
    cache.__class__ = obj.__class__
    cache.__dict__ = obj.__dict__


class CustomizedPylibmcClient(Client):
    """This client implements some simplifications
    to ease the application code.
    """

    def incr(self, key, delta=1):
        """Set the delta value if there's no key yet."""
        try:
            Client.incr(self, key, delta)
        except NotFound:
            Client.set(self, key, delta)

    def decr(self, key, delta=1):
        try:
            Client.incr(self, key, delta)
        except NotFound:
            Client.set(self, key, delta)


def set_real_cache():
    """Set the cache according to the settings."""
    if settings.MEMCACHE_SERVERS:
        if _pylibmc_available:
            servers = CustomizedPylibmcClient(settings.MEMCACHE_SERVERS, binary=True)
            servers.set_behaviors({'tcp_nodelay': True, 'no_block': True})
        else:
            servers = settings.MEMCACHE_SERVERS
        _set_cache(MemcachedCache(servers, key_prefix=settings.CACHE_PREFIX))
    else:
        _set_cache(SimpleCache())

    if settings.DEBUG:
        global cache
        cache = CacheDebugProxy(cache)

    global request_cache
    request_cache = RequestCache(cache)


def set_test_cache():
    """Enable a simple cache for unittests."""
    _set_cache(SimpleCache())


class RequestCache(object):
    """A helper cache to cache the requested stuff in a threadlocal."""
    def __init__(self, real_cache):
        self.real_cache = real_cache
        self.request_cache = _request_cache

    def get(self, key):
        if local_has_key('cache'):
            try:
                return self.request_cache[key]
            except KeyError:
                val = self.real_cache.get(key)
                if val is not None:
                    self.request_cache[key] = val

                return val
        else:
            return self.real_cache.get(key)

    def set(self, key, value, timeout=None):
        if local_has_key('cache'):
            self.request_cache[key] = value
        return self.real_cache.set(key, value, timeout)

    def delete(self, key):
        if local_has_key('cache'):
            self.request_cache.pop(key)
        self.real_cache.delete(key)


class CacheDebugProxy(object):
    """A proxy for a werkzeug.contrib.Cache which logs all queries for
    debugging purposes."""


    def _log(self, query, result):
        if current_request:
            request = current_request._get_current_object()
            if not hasattr(request, 'cache_queries'):
                request.cache_queries = list()
            ctx = find_calling_context(3)
            request.cache_queries.append((ctx, force_unicode(query), force_unicode(result)))
        return result

    def __init__(self, cache):
        self.cache = cache

    def add(self, key, value, timeout=None):
        return self._log(u'ADD %r %s (%r)' % (key, value, timeout),
            self.cache.add(key, value, timeout))

    def clear(self):
        return self._log(u'CLEAR',
            self.cache.clear())

    def dec(self, key, delta=1):
        return self._log(u'DEC %r %r' % (key, delta),
            self.cache.dec(key, delta))

    def delete(self, key):
        return self._log(u'DELETE %r' % key,
            self.cache.delete(key))

    def delete_many(self, *keys):
        return self._log(u'DELETE MANY %r' % (keys,),
            self.cache.delete_many(*keys))

    def get(self, key):
        return self._log(u'GET %r' % key,
            self.cache.get(key))

    def get_dict(self, *keys):
        return self._log(u'GET DICT %r' % (keys,),
            self.cache.get_dict(*keys))

    def get_many(self, *keys):
        return self._log(u'GET MANY %r' % (keys,),
            self.cache.get_many(*keys))

    def inc(self, key, delta=1):
        return self._log(u'INC %r %r' % (key, delta),
            self.cache.inc(key, delta))

    def set(self, key, value, timeout=None):
        return self._log(u'SET %r %s (%s)' % (key, force_unicode(repr(value)), timeout),
            self.cache.set(key, value, timeout))

    def set_many(self, mapping, timeout=None):
        _mapping = force_unicode(repr(mapping))
        return self._log(u'SET MANY %s (%s)' % (_mapping, timeout),
            self.cache.set_many(mapping, timeout))

# enable the real cache by default
set_real_cache()
