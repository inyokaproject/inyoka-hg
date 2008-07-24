#-*- coding: utf-8 -*-
"""
    inyoka.utils.user
    ~~~~~~~~~~~~~~~~~

    Serveral utilities to work with users.

    Some parts are ported from the django auth-module.

    :copyright: 2008 by Christopher Grebs, Marian Sigler.
    :license: GNU GPL
"""
import re
from md5 import md5
import random, string
from inyoka.conf import settings
from inyoka.utils.urls import href


SESSION_KEY = '_auth_user_id'


_username_re = re.compile(r'^[\w0-9_-]{1,30}(?u)$')
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


def gen_activation_key(user):
    """
    Create a new activation key.
    It's a md5 hash from the user id, the username,
    the users email and our secret key.

    :Parameters:
        user
            An user object from the user the key
            will be generated for.
    """
    return md5('%d%s%s%s' % (
        user.id, user.username,
        settings.SECRET_KEY,
        user.email
    )).hexdigest()


def check_activation_key(user, key):
    """
    Check if an activation key is correct

    :Parameters:
        user
            An user object a new key will be generated for.
            (For checking purposes)
        key
            The key that needs to be checked for the *user*.
    """
    return key == gen_activation_key(user)


def send_activation_mail(user):
    """send an activation mail"""
    from inyoka.utils.mail import send_mail
    from inyoka.utils.templating import render_template
    message = render_template('mails/activation_mail.txt', {
        'username':         user.username,
        'email':            user.email,
        'activation_key':   gen_activation_key(user)
    })
    send_mail('ubuntuusers.de - Aktivierung des Benutzers %s'
              % user.username,
              message, settings.INYOKA_SYSTEM_USER_EMAIL, [user.email])


def send_new_user_password(user):
    from inyoka.utils.mail import send_mail
    from inyoka.utils.templating import render_template
    new_password_key = ''.join(random.choice(string.lowercase + string.digits) for _ in range(24))
    user.new_password_key = new_password_key
    user.save()
    message = render_template('mails/new_user_password.txt', {
        'username':         user.username,
        'email':            user.email,
        'new_password_url': href('portal', 'lost_password', user.username, new_password_key),
    })
    send_mail(u'ubuntuusers.de – Neues Passwort für %s' % user.username,
              message, settings.INYOKA_SYSTEM_USER_EMAIL, [user.email])
