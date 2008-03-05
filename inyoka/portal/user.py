# -*- coding: utf-8 -*-
"""
    inyoka.portal.user
    ~~~~~~~~~~~~~~~~~~

    Our own user model used for implementing our own
    permission system and our own administration center.

    :copyright: Copyright 2007-2008 by Armin Ronacher, Christopher Grebs,
                                       Benjamin Wiegand, Christoph Hack.
    :license: GNU GPL.
"""
import os
import cPickle
from datetime import datetime
from sha import sha
from md5 import md5
from os import path
from PIL import Image
from StringIO import StringIO
from django.db import models
from django.conf import settings
from django.utils.encoding import smart_str
from django.core import validators
from inyoka.utils.decorators import deferred
from inyoka.utils.urls import href
from inyoka.utils.captcha import generate_word
from inyoka.utils.cache import cache
from inyoka.utils.local import current_request


UNUSABLE_PASSWORD = '!'
_ANONYMOUS_USER = None


class UserBanned(Exception):
    """
    Simple exception that is raised while
    log-in to give the user a somewhat detailed
    exception.
    """


def get_hexdigest(salt, raw_password):
    """
    Returns a string of the hexdigest of the given plaintext password and salt
    using the sha1 algorithm.
    """
    raw_password, salt = smart_str(raw_password), smart_str(salt)
    return sha(salt + raw_password).hexdigest()


def check_password(raw_password, enc_password, convert_user=None):
    """
    Returns a boolean of whether the raw_password was correct.  Handles
    encryption formats behind the scenes.
    """
    salt, hsh = enc_password.split('$')
    # compatibility with old md5 passwords
    if salt == 'md5':
        result = hsh == md5(raw_password).hexdigest()
        if result and convert_user and convert_user.is_authenticated:
            convert_user.set_password(raw_password)
            convert_user.save()
        return result
    return hsh == get_hexdigest(salt, raw_password)


class Group(models.Model):
    name = models.CharField('Name', max_length=80, unique=True)
    is_public = models.BooleanField('Öffentliches Profil')

    def get_absolute_url(self):
        return href('portal', 'groups', self.name)

    def __unicode__(self):
        return self.name


class UserManager(models.Manager):

    def create_user(self, username, email, password=None):
        now = datetime.utcnow()
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
                Whether to send an activation mail or not.
                If *False* the user will be saved as active.
        """
        user = self.create_user(username, email, password)
        if not send_mail:
            # save the user as an active one
            user.is_active = True
        else:
            user.is_active = False
            send_activation_mail(user)
        user.save()
        return user

    def logout(self, request):
        request.session.pop('uid', None)
        request.user = self.get_anonymous_user()

    def authenticate(self, username, password):
        """
        Authenticate a user with `username` and `password`.

        :Raises:
            User.DoesNotExist
                If the user with `username` does not exist
            UserBanned
                If the found user was banned by an admin.
        """
        user = User.objects.get(username=username)

        if user.banned is not None:
            if not (user.banned.utctimetuple()[:3] ==
                    datetime.utcnow().utctimetuple()[:3]):
                raise UserBanned()

        if user.check_password(password, auto_convert=True):
            return user

    def get_anonymous_user(self):
        global _ANONYMOUS_USER
        if not _ANONYMOUS_USER:
            _ANONYMOUS_USER = User.objects.get(id=1)
        return _ANONYMOUS_USER

    def get_system_user(self):
        """
        This returns the system user that is controlled by inyoka itself.  It
        is the sender for welcome notices, it updates the antispam list and
        is the owner for log entries in the wiki triggered by inyoka itself.
        """
        try:
            return User.objects.get(username=settings.INYOKA_SYSTEM_USER)
        except User.DoesNotExist:
            return User.objects.create_user(settings.INYOKA_SYSTEM_USER,
                                            settings.INYOKA_SYSTEM_USER_EMAIL)


class User(models.Model):
    """User model that contains all informations about an user."""
    objects = UserManager()

    username = models.CharField('Benutzername', max_length=30, unique=True,
        validator_list=[validators.isAlphaNumeric])
    #email = models.EmailField('E-Mail-Adresse', blank=True, unique=True, null=True)
    # allow @localhost addresses for easier testing
    email = models.CharField('E-Mail-Adresse', blank=True, unique=True, null=True, max_length=50)
    password = models.CharField('Passwort', max_length=128)
    is_active = models.BooleanField('Aktiv', default=True)
    last_login = models.DateTimeField('Letzter Login', default=datetime.utcnow)
    date_joined = models.DateTimeField('Anmeldedatum', default=datetime.utcnow)
    groups = models.ManyToManyField(Group, verbose_name='Gruppen', blank=True)
    new_password_key = models.CharField(u'Bestätigungskey für ein neues '
        u'Passwort', blank=True, null=True, max_length=32)

    banned = models.DateTimeField('Gesperrt', null=True)

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
    coordinates_long = models.FloatField('Koordinaten (Breite)', blank=True, null=True)
    coordinates_lat = models.FloatField(u'Koordinaten (Länge)', blank=True, null=True)
    location = models.CharField('Wohnort', max_length=200, blank=True)
    gpgkey = models.CharField('GPG-Key', max_length=8, blank=True)
    occupation = models.CharField('Beruf', max_length=200, blank=True)
    interests = models.CharField('Interessen', max_length=200, blank=True)
    website = models.URLField('Webseite', blank=True)
    _settings = models.TextField('Einstellungen', default=cPickle.dumps({}))

    # the user can access the admin panel
    is_manager = models.BooleanField('Teammitglied (kann ins Admin-Panel)',
                                     default=False)

    # forum attribues
    forum_last_read = models.IntegerField('Letzter gelesener Post',
                                          default=0, blank=True)
    forum_read_status = models.TextField('Gelesene Beiträge', blank=True)
    forum_welcome = models.TextField('Gelesene Willkommensnachrichten',
                                     blank=True)

    # ikhaya permissions
    is_ikhaya_writer = models.BooleanField('Ikhaya Autor', default=False)

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

    is_anonymous = property(lambda x: x.id == 1)
    is_authenticated = property(lambda x: not x.is_anonymous)
    is_banned = property(lambda x: x.banned is not None)

    def set_password(self, raw_password):
        """Set a new sha1 generated password hash"""
        import random
        salt = get_hexdigest(str(random.random()), str(random.random()))[:5]
        hsh = get_hexdigest(salt, raw_password)
        self.password = '%s$%s' % (salt, hsh)

    def check_password(self, raw_password, auto_convert=False):
        """
        Returns a boolean of whether the raw_password was correct.
        """
        return check_password(raw_password, self.password,
                              convert_user=auto_convert and self or False)

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
        if request is None:
            request = current_request._get_current_object()
        context = RenderContext(request)
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
        fn = 'portal/avatars/avatar_user%d.png' % (self.id)
        pth = path.join(settings.MEDIA_ROOT, fn)
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

    def login(self, request):
        self.last_login = datetime.utcnow()
        self.save()
        request.session['uid'] = self.id
        request.session.pop('_sk', None)
        request.user = self


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
    user.avatar = user.coordinates_long = user.coordinates_lat = None
    user.icq = user.jabber = user.msn = user.aim = user.yim = \
        user.signature = user.gpgkey = user.location = \
        user.occupation = user.interests = user.website = ''
    user.save()


from inyoka.wiki.parser import parse, render, RenderContext
from inyoka.portal.utils import send_activation_mail
