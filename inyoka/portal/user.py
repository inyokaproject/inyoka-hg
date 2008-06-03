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
from django.db import models, connection
from django.core import validators
from inyoka.conf import settings
from inyoka.utils.decorators import deferred
from inyoka.utils.cache import cache
from inyoka.utils.mail import send_mail
from inyoka.utils.html import escape
from inyoka.utils.local import current_request
from inyoka.utils.storage import storage


UNUSABLE_PASSWORD = '!'
_ANONYMOUS_USER = None
DEFAULT_GROUP_ID = 1  # group id for all registered users


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
    if isinstance(raw_password, unicode):
        raw_password = raw_password.encode('utf-8')
    return sha(str(salt) + raw_password).hexdigest()


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


class Group(models.Model):
    name = models.CharField('Name', max_length=80, unique=True)
    _default_group = None

    def get_absolute_url(self):
        return href('portal', 'group', self.name)

    def __unicode__(self):
        return self.name

    @classmethod
    def get_default_group(self):
        """Return a default group for all registered users."""
        if not Group._default_group:
            Group._default_group = Group.objects.get(id=DEFAULT_GROUP_ID)
        return Group._default_group


class UserManager(models.Manager):

    def get(self, pk=None, **kwargs):
        if pk is None:
            pk = kwargs.pop('id__exact', None)
        if pk is not None:
            user = cache.get('portal/user/%d' % pk)
            if user is not None:
                return user
            kwargs['pk'] = pk
        user = models.Manager.get(self, **kwargs)
        if pk is not None:
            cache.set('portal/user/%d' % pk, user, 300)
        return user

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
    email = models.EmailField('E-Mail-Adresse', unique=True, max_length=50)
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
    skype = models.CharField('Skype', max_length=200, blank=True)
    wengophone = models.CharField('WengoPhone', max_length=200, blank=True)
    sip = models.CharField('SIP', max_length=200, blank=True)
    signature = models.TextField('Signatur', blank=True)
    coordinates_long = models.FloatField('Koordinaten (Breite)', blank=True, null=True)
    coordinates_lat = models.FloatField(u'Koordinaten (Länge)', blank=True, null=True)
    location = models.CharField('Wohnort', max_length=200, blank=True)
    gpgkey = models.CharField('GPG-Key', max_length=8, blank=True)
    occupation = models.CharField('Beruf', max_length=200, blank=True)
    interests = models.CharField('Interessen', max_length=200, blank=True)
    website = models.URLField('Webseite', blank=True)
    launchpad = models.CharField('Launchpad Nickname', max_length=50, blank=True)
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

    # member title & icon
    member_title = models.CharField('Benutzertitel', blank=True, null=True)

    def save(self):
        """
        Save method that pickles `self.settings` before and cleanup
        the cache after saving the model.
        """
        self._settings = cPickle.dumps(self.settings)
        super(User, self).save()
        cache.delete('portal/user/%s/signature' % self.id)
        cache.delete('portal/user/%s' % self.id)

    def __unicode__(self):
        return self.username

    is_anonymous = property(lambda x: x.id == 1)
    is_authenticated = property(lambda x: not x.is_anonymous)
    is_banned = property(lambda x: x.banned is not None)

    def inc_post_count(self):
        """Increment the post count in a safe way."""
        cur = connection.cursor()
        cur.execute('''
            update portal_user
               set post_count = post_count + 1
             where id = %s;
        ''', [self.id])
        cur.close()
        connection._commit()
        self.post_count += 1
        cache.delete('portal/user/%d' % self.id)

    def set_password(self, raw_password):
        """Set a new sha1 generated password hash"""
        import random
        salt = get_hexdigest(str(random.random()), str(random.random()))[:5]
        hsh = get_hexdigest(salt, raw_password)
        self.password = '%s$%s' % (salt, hsh)
        # invalidate the new_password_key
        if self.new_password_key:
            self.new_password_key = None

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
        send_mail(subject, message, from_email, [self.email])

    def get_groups(self):
        """Get groups inclusive the default group for registered users"""
        groups = self.is_authenticated and [Group.get_default_group()] or []
        groups.extend(self.groups.all())
        return groups

    @deferred
    def settings(self):
        return cPickle.loads(str(self._settings))

    @deferred
    def _readstatus(self):
        return ReadStatus(self.forum_read_status)

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
        key = 'portal/user/%d/signature' % self.id
        instructions = cache.get(key)
        if instructions is None:
            instructions = parse(self.signature).compile(format)
            cache.set(key, instructions)
        return render(instructions, context)

    @property
    def launchpad_url(self):
        return u'http://launchpad.net/~%s' % escape(self.launchpad)

    @property
    def avatar_url(self):
        if not self.avatar:
            return href('static', 'img', 'portal', 'no_avatar.png')
        return self.get_avatar_url()

    def save_avatar(self, img):
        """Save `img` to the file system."""
        image = Image.open(StringIO(img.content))
        ext = image.format
        fn = 'portal/avatars/avatar_user%d.%s' % (self.id,
             image.format.lower())
        image_path = path.join(settings.MEDIA_ROOT, fn)
        #: clear the file system
        self.delete_avatar()

        std = storage.get_keys(('max_avatar_height', 'max_avatar_width'))
        max_size = (std['max_avatar_height'], std['max_avatar_width'])
        if image.size > max_size:
            image = image.resize(max_size)
            image.save(image_path)
        else:
            f = open(image_path, 'wb')
            try:
                f.write(img.content)
            finally:
                f.close()
        self.avatar = fn

    def delete_avatar(self):
        """Delete the avater from the file system."""
        fn = self.get_avatar_filename()
        if path.exists(fn):
            os.remove(fn)
        self.avatar = None

    def get_absolute_url(self, action='show'):
        return href(*{
            'show': ('portal', 'user', self.username),
            'privmsg': ('portal', 'privmsg', 'new', self.username)
        }[action])

    def login(self, request):
        self.last_login = datetime.utcnow()
        self.save()
        request.session['uid'] = self.id
        request.session.pop('_sk', None)
        request.user = self
        # invalidate the new_password_key
        if self.new_password_key:
            self.new_password_key = None


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
from inyoka.utils.captcha import generate_word
from inyoka.utils.urls import href
from inyoka.forum.models import ReadStatus
