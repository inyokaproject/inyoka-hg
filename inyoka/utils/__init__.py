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
    return '\n'.join((dump, hash)).encode('base64')


def decode_confirm_data(data):
    dump, hash = data.decode('base64').rsplit('\n', 1)
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
