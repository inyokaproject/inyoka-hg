# -*- coding: utf-8 -*-
"""
    inyoka.utils.storage
    ~~~~~~~~~~~~~~~~~~~~

    Dict like interface to the portal.storage model.


    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from sqlalchemy import Table, Column, Integer, String, Text, \
                        select, bindparam
from sqlalchemy.exceptions import IntegrityError
from inyoka.utils.cache import cache
from inyoka.utils.database import metadata, session

#XXX: migration: remove the id column and rename the table
storage_table = Table('portal_storage', metadata,
    Column('id', Integer, primary_key=True),
    Column('key', String(200), index=True),
    Column('value', Text()),
)

update = storage_table.update(
        storage_table.c.key==bindparam('skey'),
        values={'value':bindparam('value')})

fetch = select([storage_table.c.value]) \
    .where(storage_table.c.key==bindparam('skey')) \
    .limit(1)

insert = storage_table.insert()

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
        results = session.execute(fetch, {'skey': key}).fetchone()
        if not results:
            return default
        else:
            value = results[0]
        self._update_cache(key, value, timeout)
        return value

    def set(self, key, value, timeout=None):
        """
        Set *key* with *value* and if needed with a
        *timeout*.
        """
        #XXX: ugly check, find a more nice solution
        rows = session.execute(fetch, {'skey': key}).fetchall()
        if rows:
            session.execute(update, {'skey': key, 'value': value})
            session.commit()
        else:
            try:
                session.execute(insert, {'key': key, 'value': value})
                session.commit()
            except IntegrityError:
                # ignore concurrent insertion
                return

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
        to_fetch = [k for k in keys if values.get(k) is None]
        if not to_fetch:
            return values
        # get the items that are not in cache using a database query
        query = select([storage_table.c.key, storage_table.c.value]) \
            .where(storage_table.c.key.in_(to_fetch))

        for key, value in session.execute(query):
            values[key] = value
            self._update_cache(key, value, timeout)
        return values

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)

    def _update_cache(self, key, value, timeout=None):
        cache.set('storage/%s' % key, value, timeout)


storage = CachedStorage()
