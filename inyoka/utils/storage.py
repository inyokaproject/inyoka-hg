# -*- coding: utf-8 -*-
"""
    inyoka.utils.storage
    ~~~~~~~~~~~~~~~~~~~~

    Dict like interface to the portal.storage model.


    :copyright: Copyright 2007 by Benjamin Wiegand.
    :license: GNU GPL.
"""
from inyoka.utils.cache import cache
from django.db import models



class Storage(models.Model):
    """
    Table for storing simple key --> value relations.
    Use the `storage` object for accessing it (it behaves like a dict).
    """
    key = models.CharField(u'Schlüssel', max_length=200)
    value = models.TextField(u'Wert')

    def __unicode__(self):
        return self.key

    class Meta:
        # since this model was stored in the portal module
        # some time ago it's table is known as portal_storage
        # instead of utils_storage as django says.
        db_table = 'portal_storage'


class CachedStorage(object):
    """
    This is a dict like interface for the `Storage` model from the portal.
    It's used to store cached values also in the database.
    """

    def get(self, key, default=None, timeout=None):
        """get *key* from the cache or if not exist return *default*"""
        value = cache.get('storage/' + key)
        if value is not None:
            return value
        try:
            value = Storage.objects.get(key=key).value
        except Storage.DoesNotExist:
            return default
        self._update_cache(key, value, timeout)
        return value

    def set(self, key, value, timeout=None):
        """
        Set *key* with *value* and if needed with a
        *timeout*.
        """
        try:
            entry = Storage.objects.get(key=key)
        except Storage.DoesNotExist:
            entry = Storage(key=key)
        entry.value = value
        entry.save()
        self._update_cache(key, value, timeout)

    def get_many(self, keys, timeout=None):
        """
        Get many cached values with just one cache hit or database query.
        """
        objects = cache.get_dict(*('storage/%s' % key for key in keys))
        values = {}
        for key, value in objects.iteritems():
            values[key[8:]] = value
        #: a list of keys that aren't yet in the cache.
        #: They are queried using a database call.
        to_fetch = [x for x in keys if values.get(x) is None]
        # get the items that are not in cache using a database query
        for obj in Storage.objects.filter(key__in=to_fetch):
            values[obj.key] = obj.value
            self._update_cache(obj.key, obj.value, timeout)
        return values

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)

    def _update_cache(self, key, value, timeout=None):
        cache.set('storage/%s' % key, value, timeout)


storage = CachedStorage()
