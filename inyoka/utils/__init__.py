# -*- coding: utf-8 -*-
"""
    inyoka.utils
    ~~~~~~~~~~~~

    Various application independent utilities.

    :copyright: Copyright 2008 by Marian Sigler.
    :license: GNU GPL.
"""

from os import path, rmdir, mkdir
import cPickle
try:
    from hashlib import sha1
except ImportError:
    from sha import sha as sha1
from inyoka.conf import settings


def encode_confirm_data(data):
    dump = cPickle.dumps(data)
    hash = sha1(dump + settings.SECRET_KEY).digest()
    return (dump + hash).encode('base64').replace('+', '_')


def decode_confirm_data(data):
    data = data.replace('_', '+').decode('base64')
    dump = data[:-20]
    hash = data[-20:]
    if sha1(dump + settings.SECRET_KEY).digest() != hash:
        raise ValueError
    return cPickle.loads(dump)


def create_media_folders(delete=False):
    for folder in settings.MEDIA_DIRS:
        pth = path.join(settings.MEDIA_ROOT, folder)
        if path.exists(pth):
            if delete:
                rmdir(pth)
                mkdir(pth)


class classproperty(object):
    """
    A mix out of the built-in `classmethod` and
    `property` so that we can achieve a property
    that is not bound to an instance.

    Example::

        >>> class Foo(object):
        ...     bar = 'baz'
        ...
        ...     @classproperty
        ...     def bars(cls):
        ...         return [cls.bar]
        ...
        >>> Foo.bars
        ['baz']
    """

    def __init__(self, func, name=None):
        self.func = func
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = func.__doc__

    def __get__(self, desc, cls):
        value = self.func(cls)
        return value

