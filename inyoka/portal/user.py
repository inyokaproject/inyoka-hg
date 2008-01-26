# -*- coding: utf-8 -*-
"""
    inyoka.portal.user
    ~~~~~~~~~~~~~~~~~~

    Our own user model used for implementing our own
    permission system and our own administration center.

    :copyright: Copyright 2007 by Armin Ronacher, Christopher Grebs,
                                  Benjamin Wiegand, Christoph Hack.
    :license: GNU GPL.
"""
from sha import sha
import os
import cPickle
import datetime
from os import path
from PIL import Image
from StringIO import StringIO
from django.db import models
from django.conf import settings
from django.utils.encoding import smart_str
from django.core.cache import cache
from django.core import validators
from django.db.models.manager import EmptyManager
from inyoka.utils import deferred
from inyoka.utils.urls import href
from inyoka.utils.captcha import generate_word
from inyoka.middlewares.registry import r


UNUSABLE_PASSWORD = '!'


def get_hexdigest(salt, raw_password):
    """
    Returns a string of the hexdigest of the given plaintext password and salt
    using the sha1 algorithm.
    """
    raw_password, salt = smart_str(raw_password), smart_str(salt)
    return sha(salt + raw_password).hexdigest()


def check_password(raw_password, enc_password):
    """
    Returns a boolean of whether the raw_password was correct. Handles
    encryption formats behind the scenes.
    """
    salt, hsh = enc_password.split('$')
    return hsh == get_hexdigest(salt, raw_password)


class Group(models.Model):
    name = models.CharField('Name', max_length=80, unique=True)

    def get_absolute_url(self):
        return href('portal', 'groups', self.name)

    def __unicode__(self):
        return self.name


class UserManager(models.Manager):

    def create_user(self, username, email, password=None):
        now = datetime.datetime.now()
        user = self.model(
            None, username,
            email.strip().lower(),
            'placeholder', False,
            now, now
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def register_user(self, username, email, password, send_mail=True):
        """
        Create a new inactive user and send him an
        activation e-mail.

        :Parameters:
            username
                The username for the new user.
            email
                The user's email.
                (It's also where the activation mail will be sent to.)
            password
                The user's password.
            send_mail
                For debugging purposes. Wheter to send an activation mail or not.
                If *False* the user will be saved as active.
        """
        user = self.create_user(username, email, password)
        if not send_mail:
            # save the user as an active one
            user.is_active = True
        else:
            user.is_active = False

        if send_mail:
            send_activation_mail(user)

        return user


class User(models.Model):
    """User model that contains all informations about an user."""
    objects = UserManager()

    username = models.CharField('Benutzername', max_length=30, unique=True,
        validator_list=[validators.isAlphaNumeric])
    email = models.EmailField('E-Mail Adresse', blank=True)
    password = models.CharField('Passwort', max_length=128)
    is_active = models.BooleanField('Aktiv', default=True)
    last_login = models.DateTimeField('Letzter Login', default=datetime.datetime.now)
    date_joined = models.DateTimeField('Angemeldet', default=datetime.datetime.now)
    groups = models.ManyToManyField(Group, verbose_name='Gruppen', blank=True)

    # profile attributes
    post_count = models.IntegerField(u'Beiträge', default=0)
    avatar = models.ImageField('Avatar', upload_to='portal/avatars',
                                blank=True, null=True)
    jabber = models.CharField('Jabber', max_length=200, blank=True)
    icq = models.CharField('ICQ', max_length=16, blank=True)
    msn = models.CharField('MSN', max_length=200, blank=True)
    aim = models.CharField('AIM', max_length=200, blank=True)
    yim = models.CharField('YIM', max_length=200, blank=True)
    signature = models.TextField('Signatur', blank=True)
    coordinates = models.CharField('Koordinaten', max_length=255,
                                   blank=True)
    location = models.CharField('Wohnort', max_length=200, blank=True)
    occupation = models.CharField('Beruf', max_length=200, blank=True)
    interests = models.CharField('Interessen', max_length=200, blank=True)
    website = models.URLField('Webseite', blank=True)
    _settings = models.TextField('Einstellungen', default=cPickle.dumps({}))

    #XXX: permissions

    # forum attribues
    forum_last_read = models.IntegerField('Letzter gelesener Post', default=0)

    def save(self):
        """
        Save method that pickles `self.settings` before and cleanup
        the cache after saving the model.
        """
        self._settings = cPickle.dumps(self.settings)
        super(User, self).save()
        cache.delete('user/%s/profile' % self.id)

    def __unicode__(self):
        return self.username

    def is_anonymous(self):
        """A logged in user is not anonymus."""
        return False

    def is_authenticated(self):
        return True

    def set_password(self, raw_password):
        """Set a new sha1 generated password hash"""
        import random
        salt = get_hexdigest(str(random.random()), str(random.random()))[:5]
        hsh = get_hexdigest(salt, raw_password)
        self.password = '%s$%s' % (salt, hsh)

    def check_password(self, raw_password):
        """
        Returns a boolean of whether the raw_password was correct.
        """
        return check_password(raw_password, self.password)

    def set_unusable_password(self):
        """Sets a value that will never be a valid hash"""
        self.password = UNUSABLE_PASSWORD

    def has_usable_password(self):
        return self.password != UNUSABLE_PASSWORD

    def email_user(self, subject, message, from_email=None):
        """Sends an e-mail to this User."""
        from django.core.mail import send_mail
        send_mail(subject, message, from_email, [self.email])

    @deferred
    def settings(self):
        return cPickle.loads(str(self._settings))

    @property
    def rendered_signature(self):
        return self.render_signature()

    def render_signature(self, request=None, format='html', nocache=False):
        """Render the user signature and cache it if `nocache` is `False`."""
        context = RenderContext(request or r.request)
        if nocache or self.id is None or format != 'html':
            return parse(self.signature).render(context, format)
        key = 'user/%d/profile' % self.id
        instructions = cache.get(key)
        if instructions is None:
            instructions = parse(self.signature).compile(format)
            cache.set(key, instructions)
        return render(instructions, context)

    @property
    def avatar_url(self):
        if not self.avatar:
            return href('static', 'img', 'portal', 'no_avatar.png')
        return self.get_avatar_url()

    def save_avatar(self, img):
        """Save the avater to the file system."""
        avatar = Image.open(StringIO(img.content))
        if avatar.size > settings.AVATAR_SIZE:
            avatar = avatar.resize(settings.AVATAR_SIZE)
        actual_path = self.get_avatar_filename()
        ext = path.splitext(img.filename)[1][1:]
        fn = 'portal/avatars/avatar_user%d.%s' % (self.id, ext)
        if not actual_path:
            pth = path.join(settings.MEDIA_ROOT, fn)
        else:
            pth = actual_path
        ext = path.splitext(img.filename)[1]
        avatar.save(pth, "PNG")
        self.avatar = fn

    def delete_avatar(self):
        """Delete the avater from the file system."""
        fn = self.get_avatar_filename()
        if path.exists(fn):
            os.remove(fn)
        self.avatar = None

    def get_absolute_url(self, action='show'):
        return href(*{
            'show': ('portal', 'users', self.username),
            'privmsg': ('portal', 'privmsg', 'new', self.username)
        }[action])


def deactivate_user(user):
    """
    This deactivates a user, removes all personal information and creates a
    random anonymous name.
    """
    def _set_anonymous_name():
        """Sets the user's name to a random string"""
        new_name = generate_word()
        try:
            User.objects.get(username=new_name)
        except User.DoesNotExist:
            user.username = new_name
        else:
            _set_anonymous_name()

    _set_anonymous_name()
    user.is_active = 0
    user.avatar = None
    user.icq = user.jabber = user.msn = user.aim = user.yim = \
        user.signature = user.coordinates = user.location = \
        user.occupation = user.interests = user.website = ''
    user.save()


def get_system_user():
    """
    This returns the system user that is controlled by inyoka itself. It
    is the sender for welcome notices, it updates the antispam list and
    is the owner for log entries in the wiki triggered by inyoka itself.
    """
    try:
        return User.objects.get(username=settings.INYOKA_SYSTEM_USER)
    except User.DoesNotExist:
        return User.objects.create_user(settings.INYOKA_SYSTEM_USER,
                                        settings.INYOKA_SYSTEM_USER_EMAIL)


class AnonymousUser(object):
    """Represents a not logged in user."""
    id = None
    username = ''
    is_active = False
    groups = property(lambda s: EmptyManager())
    __unicode__ = lambda s: u'AnonymusUser'
    __str__ = lambda s: 'AnonymusUser'
    __eq__ = lambda s, o: isinstance(o, s.__class__)
    __ne__ = lambda s, o: not s.__eq__(o)
    __hash__ = lambda s: 1
    is_anonymous = lambda s: True
    is_authenticated = lambda s: False

    def __init__(self):
        pass

    def save(self):
        raise NotImplementedError

    def delete(self):
        raise NotImplementedError

    def set_password(self, raw_password):
        raise NotImplementedError

    def check_password(self, raw_password):
        raise NotImplementedError


from inyoka.wiki.parser import parse, render, RenderContext
from inyoka.utils.user import send_activation_mail
