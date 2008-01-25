#-*- coding: utf-8 -*-
"""
    inyoka.utils.user
    ~~~~~~~~~~~~~~~~~

    Serveral utilities to work with users.

    Some parts are ported from the django auth-module.

    :copyright: 2008 by Christopher Grebs, Marian Sigler.
    :license: GNU GPL
"""
import datetime
from md5 import md5
from sha import sha
from django.conf import settings
from inyoka.utils.captcha import generate_word


SESSION_KEY = '_auth_user_id'


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
    from django.core.mail import send_mail
    message = render_template('mails/activation_mail.txt', {
        'username':         user.username,
        'email':            user.email,
        'activation_key':   gen_activation_key(user)
    })
    send_mail('ubuntuusers.de - Aktivierung des Benutzers %s'
              % user.username,
              message, settings.INYOKA_SYSTEM_USER_EMAIL, [user.email])


def send_new_user_password(user):
    from django.core.mail import send_mail
    password = generate_word()
    user.set_password(password)
    user.save()
    message = render_template('mails/new_user_password.txt', {
        'username': user.username,
        'email':    user.email,
        'password':   password
    })
    send_mail((u'ubuntuusers.de - Aktivierung des Benutzers %s' % user.username),
              message, settings.INYOKA_SYSTEM_USER_EMAIL, [user.email])


def authenticate(username, password):
    """
    If the given credentials are valid, return a User object.
    """
    try:
        user = User.objects.get(username=username)
        if user.check_password(password):
            return user
    except User.DoesNotExist:
        return None


def login(request, user):
    if user is None:
        user = request.user
    user.last_login = datetime.datetime.now()
    user.save()
    request.session[SESSION_KEY] = user.id
    if hasattr(request, 'user'):
        request.user = user


def logout(request):
    """
    Remove the authenticated user's ID from the request.
    """
    try:
        del request.session[SESSION_KEY]
    except KeyError:
        pass
    if hasattr(request, 'user'):
        from inyoka.portal.user import AnonymousUser
        request.user = AnonymousUser()


def get_user(request):
    from inyoka.portal.user import AnonymousUser
    try:
        user_id = request.session[SESSION_KEY]
        user = User.objects.get(pk=user_id)
    except (User.DoesNotExist, KeyError):
        user = AnonymousUser()
    return user

# circular imports
from inyoka.portal.user import User
from inyoka.utils.templating import render_template
