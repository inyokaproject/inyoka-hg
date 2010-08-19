# -*- coding: utf-8 -*-
"""
    inyoka.forum.compat
    ~~~~~~~~~~~~~~~~~~~

    Compatibility modules to ease integration with other apps.  This module
    exists mostly to wrap some django models.

    :copyright: 2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import cPickle
from datetime import datetime
from sqlalchemy import Table, Column, Integer, ForeignKey, Boolean, String, \
    DateTime, Text
from sqlalchemy.orm import relationship
from inyoka.wiki.parser import RenderContext, parse, render
from inyoka.portal.user import DEFAULT_GROUP_ID
from inyoka.utils.database import Model
from inyoka.utils.urls import href
from inyoka.utils.local import current_request
from inyoka.utils.cache import cache
from inyoka.utils.decorators import deferred


# set up the mappers for sqlalchemy
# ---------------------------------
#
# Please note that those portal_* tables should not be used too much
# to stay in sync with Django.  If modify something here, modify it in
# the appropriate portal model too!
#
# If you have time take a look if everything's in sync!

from inyoka.utils.database import metadata
user_group_table = Table('portal_user_groups', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, ForeignKey('portal_user.id'), nullable=False),
    Column('group_id', Integer, ForeignKey('portal_group.id'), nullable=False),
)


class SAGroup(Model):
    __tablename__ = 'portal_group'

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False, unique=True)
    is_public = Column(Boolean, default=1, nullable=False)
    permissions = Column(Integer, default=0, nullable=False)
    icon = Column(String(100), nullable=True) #XXX: Use Django to modify that column!

    _default_group = None

    @property
    def icon_url(self):
        if not self.icon:
            return None
        return href('media', self.icon)

    def get_absolute_url(self, action=None):
        return href('portal', 'groups', self.name)

    @classmethod
    def get_default_group(self):
        """Return a default group for all registered users."""
        if not SAGroup._default_group:
            SAGroup._default_group = SAGroup.query.get(int(DEFAULT_GROUP_ID))
        return SAGroup._default_group

    def __unicode__(self):
        return self.name


class SAUser(Model):
    __tablename__ = 'portal_user'

    id = Column(Integer, primary_key=True)
    username = Column(String(30), nullable=False, unique=True)
    email = Column(String(50), unique=True, nullable=False)
    password = Column(String(128), nullable=False)
    status = Column(Integer, nullable=False)
    last_login = Column(DateTime, nullable=False, default=datetime.utcnow)
    date_joined = Column(DateTime, nullable=False, default=datetime.utcnow)
    new_password_key = Column(String(32), nullable=True)
    banned_until = Column(DateTime, nullable=True, default=datetime.utcnow)
    # profile attributes
    post_count = Column(Integer, default=0, nullable=False)
    avatar = Column(String(100), nullable=False) # XXX: Use Django to modify that column!
    jabber = Column(String(200), nullable=False)
    icq = Column(String(16), nullable=False)
    msn = Column(String(200), nullable=False)
    aim = Column(String(200), nullable=False)
    yim = Column(String(200), nullable=False)
    skype = Column(String(200), nullable=False)
    wengophone = Column(String(200), nullable=False)
    sip = Column(String(200), nullable=False)
    signature = Column(Text, nullable=False)
    coordinates_long = Column(String(200), nullable=True)
    coordinates_lat = Column(String(200), nullable=True)
    location = Column(String(200), nullable=False)
    gpgkey = Column(String(8), nullable=False)
    occupation = Column(String(200), nullable=True)
    interests = Column(String(200), nullable=True)
    website = Column(String(200), nullable=False)
    launchpad = Column(String(50), nullable=True)
    _settings = Column(Text, nullable=False)
    _permissions = Column(Integer, default=0, nullable=False)
    # forum attributes
    forum_last_read = Column(Integer, default=0, nullable=False)
    forum_read_status = Column(Text, nullable=False)
    forum_welcome = Column(Text, nullable=False)
    member_title = Column(String(200), nullable=True)

    primary_group_id = Column(Integer, ForeignKey('portal_group.id'), nullable=True)

    # relationship configuration
    groups = relationship(SAGroup, secondary=user_group_table, lazy='dynamic')

    # Shortcut properties
    is_anonymous = property(lambda x: x.id == 1)
    is_authenticated = property(lambda x: not x.is_anonymous)
    is_active = property(lambda x: x.status == 1)
    is_banned = property(lambda x: x.status == 2)
    is_deleted = property(lambda x: x.status == 3)

    def get_absolute_url(self, action=None):
        return href('portal', 'user', self.username)

    @property
    def avatar_url(self):
        if not self.avatar:
            return href('static', 'img', 'portal', 'no_avatar.png')
        return href('media', self.avatar)

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

    @deferred
    def settings(self):
        return cPickle.loads(str(self._settings))

    @deferred
    def primary_group(self):
        if self.primary_group_id is None:
            # we use the first assigned group as the primary one
            groups = self.groups.all()
            return groups and groups[0] or SAGroup.get_default_group()
        return SAGroup.query.get(self.primary_group_id)

    def __unicode__(self):
        return self.username
