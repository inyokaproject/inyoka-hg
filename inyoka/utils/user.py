#-*- coding: utf-8 -*-
"""
    inyoka.utils.user
    ~~~~~~~~~~~~~~~~~

    Serveral utilities to work with users.

    Some parts are ported from the django auth-module.

    :copyright: 2008 by Christopher Grebs, Marian Sigler.
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
from inyoka.portal.user import User
from inyoka.portal.utils import send_new_user_password
from inyoka.utils import encode_confirm_data
from inyoka.utils.html import escape
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


def deactivate_user(user):
    """
    This deactivates a user and removes all personal information.
    To avoid abuse he is sent an email allowing him to reactivate the
    within the next month.
    """

    userdata = {
        'action': 'reactivate_user',
        'id': user.id,
        'email': user.email,
        'status': user.status,
        'time': datetime.now(),
    }

    userdata = encode_confirm_data(userdata)

    subject = u'Deaktivierung deines Accounts „%s“ auf ubuntuusers.de' % \
                  user.username
    text = render_template('mails/account_deactivate.txt', {
        'user': user,
        'userdata': userdata,
    })
    user.email_user(subject, text, settings.INYOKA_SYSTEM_USER_EMAIL)

    user.status = 3
    if not user.is_banned:
        user.email = 'user%d@ubuntuusers.de.invalid' % user.id
    user.set_unusable_password()
    user.groups.remove(*user.groups.all())
    user.avatar = user.coordinates_long = user.coordinates_lat = \
        user.new_password_key = user._primary_group = None
    user.icq = user.jabber = user.msn = user.aim = user.yim = user.skype = \
        user.wengophone = user.sip = user.location = user.signature = \
        user.gpgkey = user.location = user.occupation = user.interests = \
        user.website = user.launchpad = user.member_title = ''
    user.save()


def reactivate_user(id, email, status, time):
    if (datetime.now() - time).days > 33:
        return {'failed':
                u'Seit der Löschung ist mehr als ein Monat vergangen!'}
    user = User.objects.get(id=id)
    if not user.is_deleted:
        return {
            'failed': u'Der Benutzer %s ist nicht gelöscht' %
                escape(user.username),
            'action': 'reactivate_user',
        }
    user.email = email
    user.status = status
    if user.banned_until and user.banned_until < datetime.now():
        user.status = 1
        user.banned_until = None
    user.save()
    send_new_user_password(user)
    return {
        'success': u'Der Benutzer %s wurde wiederhergestellt. Dir wurde '
                   u'eine E-Mail geschickt, mit der du dir ein neues Passwort '
                   u'setzen kannst.' % escape(user.username),
        'action': 'reactivate_user',
    }
