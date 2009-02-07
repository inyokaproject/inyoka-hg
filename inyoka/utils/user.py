#-*- coding: utf-8 -*-
"""
    inyoka.utils.user
    ~~~~~~~~~~~~~~~~~

    Serveral utilities to work with users.

    Some parts are ported from the django auth-module.

    :copyright: 2008 by Christopher Grebs, Marian Sigler,
        Benjamin Wiegand.
    :license: GNU GPL
"""
import random, string, re
try:
    from hashlib import md5, sha1
except ImportError:
    from md5 import md5
    from sha import sha as sha1
from datetime import datetime
from inyoka.conf import settings
from inyoka.utils.html import escape
from inyoka.utils.mail import send_mail
from inyoka.utils.templating import render_template
from inyoka.utils.urls import href


SESSION_KEY = '_auth_user_id'


_username_re = re.compile(r'^[\w0-9_ -]{1,30}(?u)$')
_username_split_re = re.compile(r'[\s_]+')


def is_valid_username(name):
    """Check if the username entered is a valid one."""
    try:
        normalize_username(name)
    except ValueError:
        return False
    return True


def normalize_username(name):
    """Normalize the username."""
    if _username_re.search(name) is not None:
        rv = ' '.join(_username_split_re.split(name)).strip()
        if rv:
            return rv
    raise ValueError('invalid username')


def gen_activation_key(user, legacy=False):
    """
    It's calculated using a sha1 hash of the user id, the username,
    the users email and our secret key and shortened to ensure the
    activation link has less then 80 chars.

    :Parameters:
        user
            An user object from the user the key
            will be generated for.
    """
    if legacy:
        return md5(('%d%s%s%s' % (
            user.id, user.username,
            settings.SECRET_KEY,
            user.email
        )).encode('utf8')).hexdigest()
    return sha1(('%d%s%s%s' % (
        user.id, user.username,
        settings.SECRET_KEY,
        user.email
    )).encode('utf8')).digest()[:9].encode('base64') \
        .strip('\n=').replace('/', '_').replace('+', '-')


def check_activation_key(user, key, legacy=False):
    """
    Check if an activation key is correct

    :Parameters:
        user
            An user object a new key will be generated for.
            (For checking purposes)
        key
            The key that needs to be checked for the *user*.
    """
    return key == gen_activation_key(user, legacy)


def get_hexdigest(salt, raw_password):
    """
    Returns a string of the hexdigest of the given plaintext password and salt
    using the sha1 algorithm.
    """
    if isinstance(raw_password, unicode):
        raw_password = raw_password.encode('utf-8')
    return sha1(str(salt) + raw_password).hexdigest()


def check_password(raw_password, enc_password, convert_user=None):
    """
    Returns a boolean of whether the raw_password was correct.  Handles
    encryption formats behind the scenes.
    """
    if isinstance(raw_password, unicode):
        raw_password = raw_password.encode('utf-8')
    salt, hsh = enc_password.split('$')
    # compatibility with old md5 passwords
    if salt == 'md5':
        result = hsh == md5(raw_password).hexdigest()
        if result and convert_user and convert_user.is_authenticated:
            convert_user.set_password(raw_password)
            convert_user.save()
        return result
    return hsh == get_hexdigest(salt, raw_password)
