# -*- coding: utf-8 -*-
"""
    test_storage
    ~~~~~~~~~~~~

    This module tests the the storage object that uses a combination of cache
    and database storing..

    :copyright: Copyright 2008 by Benjamin Wiegand.
    :license: GNU GPL.
"""
import time
from inyoka.utils.storage import storage, Storage
from inyoka.utils.cache import cache


def test_set():
    def _compare(key, value):
        assert value == Storage.objects.get(key=key).value == \
            cache.get('storage/' + key) == storage[key]
    storage['test'] = 'foo'
    storage['test'] = 'bar'
    _compare('test', 'bar')
    storage.set('test', 'boo', 1)
    _compare('test', 'boo')
    time.sleep(3)
    assert None == cache.get('storage/test')
    storage['foo'] = 'bar'
    storage['boo'] = 'far'
    assert storage.get_many(['foo', 'boo', 'nonexisting']) == {
        'foo': 'bar',
        'boo': 'far'
    }
