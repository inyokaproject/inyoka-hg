# -*- coding: utf-8 -*-
"""
    inyoka.utils.cache
    ~~~~~~~~~~~~~~~~~~

    Holds the current active cache object.

    :copyright: 2008-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from werkzeug.contrib.cache import MemcachedCache, SimpleCache, _test_memcached_key

from inyoka.conf import settings


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

    def get_dict(self, *keys):
        key_mapping = {}
        have_encoded_keys = False
        for idx, key in enumerate(keys):
            if isinstance(key, unicode):
                encoded_key = key.encode('utf-8')
                have_encoded_keys = True
            else:
                encoded_key = key
            if self.key_prefix:
                encoded_key = self.key_prefix + encoded_key
            if _test_memcached_key(key):
                key_mapping[encoded_key] = key

        # calculate key hash to get local-cached multi-key
        # values.
        if not hasattr(local, 'cache'):
            local.cache = {}

        kh = hash(u''.join(key_mapping.keys()))
        if kh in local.cache:
            return local.cache[kh]

        # the keys call here is important because otherwise cmemcache
        # does ugly things.  What exaclty I don't know, i think it does
        # Py_DECREF but quite frankly i don't care.
        d = rv = self._client.get_multi(key_mapping.keys())
        if have_encoded_keys or self.key_prefix:
            rv = {}
            for key, value in d.iteritems():
                rv[key_mapping[key]] = value
        if len(rv) < len(keys):
            for key in keys:
                if key not in rv:
                    rv[key] = None
        local.cache[kh] = rv
        return rv


def _set_cache(obj):
    cache.__class__ = obj.__class__
    cache.__dict__ = obj.__dict__


def set_real_cache():
    """Set the cache according to the settings."""
    if settings.MEMCACHE_SERVERS:
        _set_cache(InyokaMemcachedCache(settings.MEMCACHE_SERVERS))
    else:
        _set_cache(SimpleCache())


def set_test_cache():
    """Enable a simple cache for unittests."""
    _set_cache(SimpleCache())


# enable the real cache by default
set_real_cache()
