# -*- coding: utf-8 -*-
"""
    inyoka.middlewares.registry
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This module implements a per request registry. This allows use to use the
    special `r` variable in the base module. It also imports all applications
    so that boostrapping code is executed.

    :copyright: Copyright 2007 by Armin Ronacher
    :license: GNU GPL.
"""
from threading import local

_locals = local()
_empty_storage = {}


class Registry(object):
    """
    The registry we use.
    """

    def __init__(self):
        raise TypeError('cannot create %r instances' %
                        self.__class__.__name__)

    def __getattr__(self, name):
        return getattr(_locals, 'storage', _empty_storage).get(name)

    def __setattr__(self, name, value):
        storage = getattr(_locals, 'storage', _empty_storage)
        if storage is not _empty_storage:
            storage[name] = value

    @property
    def request(self):
        return getattr(_locals, 'request', None)

    def isolated_registry(self, name):
        return IsolatedRegistry(self, name)


class IsolatedRegistry(object):
    """
    Like the normal registry but with an isolated namespace.
    """

    def __init__(self, singleton, name):
        self.__singleton = singleton
        self.__name = name

    def __getattr__(self, name):
        storage = getattr(self.__singleton, self.__name)
        if storage is not None:
            return storage.get(name)

    def __setattr__(self, name, value):
        storage = getattr(self.__singleton, self.__name)
        if storage is None:
            storage = {}
            setattr(self.__singleton, self.__name, storage)
        storage[name] = value


class RegistryMiddleware(object):

    def process_request(self, request):
        _locals.request = request
        _locals.storage = {}


r = object.__new__(Registry)
