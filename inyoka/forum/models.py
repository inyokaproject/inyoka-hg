# -*- coding: utf-8 -*-
"""
    inyoka.forum.models
    ~~~~~~~~~~~~~~~~~~~

    Database models for the forum.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from __future__ import division
import os
import cPickle
import operator
from os import path
from hashlib import md5
from PIL import Image
from time import time
from StringIO import StringIO
from datetime import datetime
from mimetypes import guess_type
from itertools import groupby
from inyoka.utils.database import db

from inyoka.conf import settings
from inyoka.utils.text import get_new_unique_filename
from inyoka.utils.dates import timedelta_to_seconds
from inyoka.utils.html import escape
from inyoka.utils.urls import href
from inyoka.utils.highlight import highlight_code
from inyoka.utils.search import search
from inyoka.utils.cache import cache
from inyoka.utils.local import current_request
from inyoka.utils.decorators import deferred

from inyoka.forum.acl import filter_invisible, get_privileges, CAN_READ, \
    filter_visible
from inyoka.forum.compat import SAUser

# Import Django models here so that South can find them
from inyoka.forum.django_models import *


# initialize PIL to make Image.ID available
Image.init()
SUPPORTED_IMAGE_TYPES = ['image/%s' % m.lower() for m in Image.ID]

POSTS_PER_PAGE = 15
TOPICS_PER_PAGE = 30
CACHE_PAGES_COUNT = 5


class UbuntuVersion(object):
    """holds the ubuntu versions. implement this as a model in SA!"""
    def __init__(self, number, codename, lts=False, active=True, class_=None,
                 current=False):
        self.number = number
        self.codename = codename
        self.lts = lts
        self.active = active
        self.class_ = class_
        self.current = current
        self.link = href('wiki', codename)

    def __str__(self):
        return u'%s (%s)' % (self.number, self.codename)


UBUNTU_VERSIONS = [
    UbuntuVersion('keine', 'Keine Angabe', active=True),
    UbuntuVersion('4.10', 'Warty Warthog', active=False),
    UbuntuVersion('5.04', 'Hoary Hedgehog', active=False),
    UbuntuVersion('5.10', 'Breezy Badger', active=False),
    UbuntuVersion('6.06', 'Dapper Drake', lts=True),
    UbuntuVersion('6.10', 'Edgy Eft', active=False),
    UbuntuVersion('7.04', 'Feisty Fawn', active=False),
    UbuntuVersion('7.10', 'Gutsy Gibbon', active=False),
    UbuntuVersion('8.04', 'Hardy Heron', lts=True),
    UbuntuVersion('8.10', 'Intrepid Ibex', active=False),
    UbuntuVersion('9.04', 'Jaunty Jackalope'),
    UbuntuVersion('9.10', 'Karmic Koala'),
    UbuntuVersion('10.04', 'Lucid Lynx', lts=True, current=True),
    UbuntuVersion('10.10', 'Maverick Meerkat', class_='unstable'),
]

UBUNTU_DISTROS_LEGACY = {
    'keine': 'Keine Angabe',
    'edubuntu': 'Edubuntu',
    'kubuntu': 'Kubuntu',
    'kubuntu-kde4': u'Kubuntu (KDE 4)',
    'server': 'Server',
    'ubuntu': 'Ubuntu',
    'xubuntu': 'Xubuntu'
}

UBUNTU_DISTROS = {
    'keine': 'Keine Angabe',
    'edubuntu': 'Edubuntu',
    'kubuntu': 'Kubuntu',
    'server': 'Server',
    'ubuntu': 'Ubuntu',
    'xubuntu': 'Xubuntu'
}


def fix_plaintext(text):
    text = escape(text)
    text = text.replace('\n', '<br />')
    return text


class ForumQuery(db.Query):

    def _get_slugs(self):
        slug_map = cache.get('forum/slugs')
        if slug_map is None:
            slug_map = dict(db.session.query(Forum.id, Forum.slug).all())
            cache.set('forum/slugs', slug_map)
        return slug_map

    def get(self, ident):
        # We unify the usage internally to query the id but accept an slug too.
        # To cache the result we use the slug as it's used in the forum view too
        mapper = self._mapper_zero()
        slugs = self._get_slugs()

        if isinstance(ident, (int, float, long)):
            ident = slugs.get(ident)

        if ident is None:
            return None

        forum = self.get_cached(ident)
        return forum

    def get_eager(self):
        options = (db.eagerload('last_post'), db.eagerload('last_post.author'))
        return db.session.query(Forum).options(*options)

    def get_all_forums_cached(self):
        slugs = self._get_slugs()
        reverted = dict((y, x) for x, y in slugs.iteritems())
        cache_keys = ['forum/forums/%s' % s for s in reverted]
        forums = cache.get_dict(*cache_keys)

        # fill forum cache
        missing = [reverted[key.split('/')[-1]] for key, value in forums.iteritems()
                   if value is None]
        if missing:
            query = self.get_eager().filter(Forum.id.in_(missing))
            missing_objects = dict((x.slug, x) for x in query)
            for key, value in forums.iteritems():
                if value is None:
                    forums[key] = missing_objects[key.split('/')[-1]]
            cache.set_many(forums)
        else:
            # merge forums into sqlalchemy session again
            objects = forums.itervalues()
            for key, value in forums.iteritems():
                forums[key] = db.session.merge(value, load=False)

        return forums

    def get_cached(self, slug=None):
        if slug:
            # we only select one forum and query only one if it's
            # not cached yet.
            query = self.get_eager().filter_by(slug=slug)
            forum = cache.get('forum/forums/%s' % slug)
            if forum is None:
                forum = query.one()
                cache.set('forum/forums/%s' % slug, forum)
            else:
                forum = db.session.merge(forum, load=False)
            return forum
        # return all forums instead
        return self.get_all_forums_cached().values()

    def get_forums_filtered(self, user, priv=CAN_READ, reverse=False):
        forums = self.get_cached()
        privileges = get_privileges(user, [f.id for f in forums])
        if reverse:
            return filter_visible(user, forums, priv, privileges)
        return filter_invisible(user, forums, priv, privileges)


class ForumMapperExtension(db.MapperExtension):

    def after_update(self, mapper, connection, instance):
        cache.delete('forum/forums/%s' % instance.slug)
        return db.EXT_CONTINUE

    def after_insert(self, mapper, connection, instance):
        cache.delete('forum/forums/%s' % instance.slug)
        cache.delete('forum/slugs')
        return db.EXT_CONTINUE

    def after_delete(self, mapper, connection, instance):
        self.after_insert(self, mapper, connection, instance)
        return db.EXT_CONTINUE


class TopicQuery(db.Query):

    def filter_overview(self, forum_id):
        options = (db.eagerload('author'), db.eagerload_all('last_post.author'),
                   db.eagerload_all('first_post.author'))
        order = (Topic.sticky.desc(), Topic.last_post_id.desc())
        return self.options(*options).filter_by(forum_id=forum_id).order_by(*order)


class TopicMapperExtension(db.MapperExtension):

    def before_insert(self, mapper, connection, instance):
        if not instance.forum and instance.forum_id:
            instance.forum = Forum.query.get(int(instance.forum_id))
        if not instance.forum or instance.forum.parent_id is None:
            raise ValueError('Invalid Forum')
        return db.EXT_CONTINUE

    def after_insert(self, mapper, connection, instance):
        parent_ids = list(p.id for p in instance.forum.parents)
        parent_ids.append(instance.forum_id)
        if parent_ids:
            db.session.execute(Forum.__table__.update(Forum.id.in_(parent_ids), {
                'topic_count': Forum.topic_count + 1
            }))
        return db.EXT_CONTINUE

    def before_delete(self, mapper, connection, instance):
        if not instance.forum:
            return

        ids = [p.id for p in instance.forum.parents[:-1]]
        ids.append(instance.forum_id)
        if not ids:
            return db.EXT_CONTINUE

        # set a new last_post_id because of integrity errors and
        # decrase the topic_count
        connection.execute(Forum.__table__.update(Forum.id.in_(ids), {
            'last_post_id': db.select([db.func.max(Post.id)], db.and_(
                Post.topic_id != instance.id,
                Topic.forum_id.in_(ids),
                Topic.id == Post.topic_id)),
            'topic_count': Forum.topic_count - 1
        }))

        connection.execute(Topic.__table__.update(Topic.id == instance.id, {
                'first_post_id': None,
                'last_post_id':  None,
        }))

        connection.execute('''
            delete from portal_subscription where topic_id = %s;
        ''', [instance.id])

        connection.execute('''
            update wiki_page set topic_id = NULL where topic_id = %s;
        ''', [instance.id])

        return db.EXT_CONTINUE

    def after_delete(self, mapper, connection, instance):
        instance.reindex()
        cache.delete('forum/reported_topic_count')
        return db.EXT_CONTINUE


class PostMapperExtension(db.MapperExtension):

    def before_insert(self, mapper, connection, instance):
        if not instance.is_plaintext:
            instance.rendered_text = instance.render_text()
        # XXX: race-conditions and other stupid staff... :/
        # require a mysql update to work properly!
        if instance.position is None:
            instance.position = connection.execute(db.select(
                [db.func.max(Post.position)+1],
                Post.topic_id == instance.topic_id)).fetchone()[0] or 0
        return db.EXT_CONTINUE

    def after_insert(self, mapper, connection, instance):
        if instance.topic.forum.user_count_posts:
            connection.execute(SAUser.__table__.update(
                SAUser.id==instance.author_id, values={
                'post_count': SAUser.post_count + 1
            }))
            cache.delete('portal/user/%d' % instance.author_id)
        values = {
            'post_count': Topic.post_count + 1,
            'last_post_id': instance.id
        }
        if instance.topic.first_post_id is None:
            values['first_post_id'] = instance.id
        connection.execute(Topic.__table__.update(
            Topic.id==instance.topic_id, values=values
        ))
        parent_ids = list(p.id for p in instance.topic.forum.parents)
        parent_ids.append(instance.topic.forum_id)
        connection.execute(Forum.__table__.update(
            Forum.id.in_(parent_ids), values={
            'post_count': Forum.post_count + 1,
            'last_post_id': instance.id
        }))
        instance.topic.forum.invalidate_topic_cache()
        search.queue('f', instance.id)
        return db.EXT_CONTINUE

    def after_update(self, mapper, connection, instance):
        search.queue('f', instance.id)
        return db.EXT_CONTINUE

    def after_delete(self, mapper, connection, instance):
        search.queue('f', instance.id)
        return db.EXT_CONTINUE

    def before_delete(self, mapper, connection, instance):
        self.deregister(mapper, connection, instance)
        return db.EXT_CONTINUE

    def deregister(self, mapper, connection, instance):
        """Remove references and decrement post counts for this topic."""
        if not instance.topic:
            return
        # This is crazy shit.  To increment or decrement we need the forums
        # up to the root (the category!) but to find a new last_post_id
        # we *only* have to search in the current forum and it's parents.
        # If we search in the category for a new last_post_id it's not save
        # to say that we get some out of the forum we need but also from
        # others if we have luck :-)
        forums_to_root = instance.topic.forum.parents
        forums_to_root.append(instance.topic.forum)
        forums = instance.topic.forum.parents[:-1]
        forums.append(instance.topic.forum)

        # and now the ids...
        forums_to_root_ids = [p.id for p in forums_to_root]
        forum_ids = [p.id for p in forums]

        # degrade user post count
        if instance.topic.forum.user_count_posts:
            connection.execute(SAUser.__table__.update(
                SAUser.id == instance.author_id, values={
                    'post_count': SAUser.post_count - 1}
            ))
            cache.delete('portal/user/%d' % instance.author_id)

        # set the last post id for the topic
        if instance.id == instance.topic.last_post_id:
            new_last_post = Post.query.filter(db.and_(
                Topic.id == instance.topic_id,
                Post.id != instance.id
            )).order_by(Post.id.desc()).first()
            connection.execute(Topic.__table__.update(
                Topic.id == instance.topic_id, values={
                    'last_post_id': new_last_post.id
            }))

        # and also look if we are the last post of the overall forum
        if instance.id == instance.topic.forum.last_post_id:
            # we cannot loop over all posts in the forum so we cheat a bit
            # with selecting the last post from the current topic.
            # Everything else would kill the server...
            new_last_post = Post.query.filter(db.and_(
                Post.id != instance.id,
                Topic.id == instance.topic.id
            )).order_by(Post.id.desc()).first()
            connection.execute(Forum.__table__.update(
                Forum.id.in_(forums_to_root_ids),
                values={'last_post_id': new_last_post.id}
            ))

        # decrement post_counts
        connection.execute(Topic.__table__.update(
            Topic.id == instance.topic_id, values={
                'post_count': Topic.post_count - 1
            }))
        forum_ids = [f.id for f in instance.topic.forum.parents]
        forum_ids.append(instance.topic.forum.id)
        connection.execute(Forum.__table__.update(
            Forum.id.in_(forums_to_root_ids), values={
                'post_count': Forum.post_count - 1
            }))

        # decrement position
        connection.execute(Post.__table__.update(db.and_(
            Post.position > instance.position,
            Post.topic_id == instance.topic_id), values={
                'position': Post.position - 1
            }
        ))


class PrivilegeMapperExtension(db.MapperExtension):

    def _erase_anonymous_cache(self, instance):
        if instance.user_id and instance.user_id == 1:
            # anonymous user, erase cache
            cache.delete('forum/acls/anonymous')

    def after_update(self, mapper, connection, instance):
        self._erase_anonymous_cache(instance)
        return db.EXT_CONTINUE

    def after_insert(self, mapper, connection, instance):
        self._erase_anonymous_cache(instance)
        return db.EXT_CONTINUE

    def after_delete(self, mapper, connection, instance):
        self._erase_anonymous_cache(instance)
        return db.EXT_CONTINUE


class Forum(db.Model):
    """
    This is a forum that may contain subforums or threads.
    If parent is None this forum is a root forum, else it's a subforum.
    Position is an integer that's used to sort the forums.  The lower position
    is, the higher the forum is displayed.
    """
    __tablename__ = 'forum_forum'

    query = db.session.query_property(ForumQuery)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.String(500), nullable=False, default='')
    parent_id = db.Column(db.Integer, db.ForeignKey('forum_forum.id'), nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    last_post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id',
                          use_alter=True, name='forum_forum_lastpost_id'),
                          nullable=True)
    post_count = db.Column(db.Integer, default=0, nullable=False)
    topic_count = db.Column(db.Integer, default=0, nullable=False)
    welcome_message_id = db.Column(db.Integer, db.ForeignKey('forum_welcomemessage.id'),
                                nullable=True)
    newtopic_default_text = db.Column(db.Text, nullable=True)
    user_count_posts = db.Column(db.Boolean, default=True, nullable=False)
    force_version = db.Column(db.Boolean, default=False, nullable=False)

    # db.relationship configuration
    topics = db.relationship('Topic', lazy='dynamic')
    _children = db.relationship('Forum', cascade='all',
        backref=db.backref('parent', remote_side=[id], cascade='all'))
    last_post = db.relationship('Post', post_update=True)

    __mapper_args__ = {'extension': (ForumMapperExtension(),
                                     db.SlugGenerator('slug', 'name')),
                       'order_by': position}

    def get_absolute_url(self, action='show'):
        if action == 'show':
            return href('forum', self.parent_id and 'forum' or 'category',
                        self.slug)
        if action in ('newtopic', 'welcome', 'subscribe', 'unsubscribe',
                      'markread'):
            return href('forum', 'forum', self.slug, action)
        if action == 'edit':
            return href('admin', 'forum', 'edit', self.id)
    @property
    def parents(self):
        """Return a list of all parent forums up to the root level."""
        parents = []
        forums = Forum.query.get_cached()
        qdct = dict((f.id, f) for f in forums)

        forum = self
        while forum.parent_id is not None:
            forum = qdct[forum.parent_id]
            parents.append(forum)
        return parents

    @property
    def children(self):
        forums = Forum.query.get_cached()
        children = [forum for forum in forums if forum.parent_id == self.id]
        return children

    def get_children_filtered(self, user, priv=CAN_READ):
        """Same as children, but check for acls if a user is given"""
        visible_forums = Forum.query.get_forums_filtered(user, priv=priv)
        return self.filter_children(visible_forums)

    def filter_children(self, forums):
        return [forum for forum in forums if forum.parent_id == self.id]

    def get_latest_topics(self, count=None):
        """
        Return a list of the latest topics in this forum. If no count is
        given the default value from the settings will be used and the whole
        output will be cached (highly recommended!).
        """
        limit = max(settings.FORUM_TOPIC_CACHE, count)
        key = 'forum/latest_topics/%d' % self.id
        topics = (limit == 100) and cache.get(key) or None

        if not topics:
            topics = Topic.query \
                .options(db.eagerload('author'),
                         db.eagerload('last_post'),
                         db.eagerload('last_post.author')) \
                .filter_by(forum_id=self.id) \
                .order_by(Topic.sticky.desc(), Topic.last_post_id.desc()) \
                .limit(limit)
            if limit == settings.FORUM_TOPIC_CACHE:
                topics = topics.all()
                cache.set(key, topics)
        else:
            merge = db.session.merge
            topics = [merge(obj, load=False) for obj in topics]

        return (count < limit) and topics[:count] or topics

    latest_topics = property(get_latest_topics)

    def get_read_status(self, user):
        """
        Determine the read status of the whole forum for a specific
        user.
        """
        if user.is_anonymous:
            return True
        return user._readstatus(self)

    def mark_read(self, user):
        """
        Mark all topics in this forum and all related subforums as
        read for the specificed user.
        """
        if user.is_anonymous:
            return
        if user._readstatus.mark(self):
            user.forum_read_status = user._readstatus.serialize()

    def find_welcome(self, user):
        """
        Return a forum with an unread welcome message if exits.
        The message itself, can be retrieved late, by reading the
        welcome_message attribute.
        """
        forums = self.parents
        forums.append(self)
        read = set()
        if user.is_authenticated and user.forum_welcome:
            read = set(int(i) for i in user.forum_welcome.split(','))
        for forum in forums:
            if forum.welcome_message_id is not None and \
               forum.id not in read:
                return forum
        return None

    def read_welcome(self, user, read=True):
        if user.is_anonymous:
            return
        status = set()
        if user.forum_welcome:
            status = set(int(i) for i in user.forum_welcome.split(','))
        if read:
            status.add(self.id)
        else:
            status.discard(self.id)
        user.forum_welcome = ','.join(str(i) for i in status)
        user.save()

    def invalidate_topic_cache(self):
        for page in xrange(CACHE_PAGES_COUNT):
            cache.delete('forum/topics/%d/%d' % (self.id, page+1))

    @staticmethod
    def get_children_recursive(forums, parent=None, offset=0):
        """
        Yield all forums sorted as in the index page, with indentation.
        `forums` must be sorted by position.
        Every entry is a tuple (offset, forum). Example usage::
            forums = Forum.query.order_by(Forum.position.asc()).all()
            for offset, f in Forum.get_children_recursive(forums):
                choices.append((f.id, u'  ' * offset + f.name))
        """
        if isinstance(parent, Forum):
            parent = parent.id
        matched_forums = filter(lambda f: f.parent_id == parent, forums)
        for f in matched_forums:
            yield offset, f
            for l in Forum.get_children_recursive(forums, f, offset + 1):
                yield l

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return '<%s id=%s slug=%s name=%s>' % (
            self.__class__.__name__,
            self.id,
            self.slug.encode('utf-8'),
            self.name.encode('utf-8')
        )


class Topic(db.Model):
    """
    A topic symbolizes a bunch of Posts (at least one) that is located inside
    a Forum.
    When creating a new topic, a new post is added to it automatically.
    """
    __tablename__ = 'forum_topic'
    __mapper_args__ = {'extension': (TopicMapperExtension(),
                                     db.SlugGenerator('slug', 'title'))}

    query = db.session.query_property(TopicQuery)

    id = db.Column(db.Integer, primary_key=True)
    forum_id = db.Column(db.Integer, db.ForeignKey('forum_forum.id'))
    title = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(50), nullable=False, index=True)
    view_count = db.Column(db.Integer, default=0, nullable=False)
    post_count = db.Column(db.Integer, default=0, nullable=False)
    sticky = db.Column(db.Boolean, default=False, nullable=False, index=True)
    solved = db.Column(db.Boolean, default=False, nullable=False)
    locked = db.Column(db.Boolean, default=False, nullable=False)
    reported = db.Column(db.Text, nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('portal_user.id'), nullable=True)
    report_claimed_by_id = db.Column(db.Integer, db.ForeignKey('portal_user.id'))
    hidden = db.Column(db.Boolean, default=False, nullable=False)
    ubuntu_version = db.Column(db.String(5), nullable=True)
    ubuntu_distro = db.Column(db.String(40), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('portal_user.id'), nullable=False)
    first_post_id = db.Column(db.Integer,
        db.ForeignKey('forum_post.id', use_alter=True, name='forum_topic_fistpost_fk'),
        nullable=True)
    last_post_id = db.Column(db.Integer,
        db.ForeignKey('forum_post.id', use_alter=True, name='forum_topic_lastpost_fk'),
        nullable=True)
    has_poll = db.Column(db.Boolean, default=False, nullable=False)

    # db.relationship configuration
    author = db.relationship(SAUser, primaryjoin=author_id == SAUser.id)
    reporter = db.relationship(SAUser, primaryjoin=reporter_id == SAUser.id)
    report_claimed_by = db.relationship(SAUser,
        primaryjoin=report_claimed_by_id == SAUser.id)
    last_post = db.relationship('Post', post_update=True,
        primaryjoin='Topic.last_post_id == Post.id')
    first_post = db.relationship('Post', post_update=True,
        primaryjoin='Topic.first_post_id == Post.id')

    forum = db.relationship(Forum)
    polls = db.relationship('Poll', backref='topic')
    posts = db.relationship('Post', backref='topic', cascade='all, delete-orphan',
        primaryjoin='Topic.id == Post.topic_id', lazy='dynamic',
        passive_deletes=True)

    def touch(self):
        """Increment the view count in a safe way."""
        self.view_count = Topic.view_count + 1

    def move(self, forum):
        """Move the topic to an other forum."""
        ids = list(p.id for p in self.forum.parents)
        ids.append(self.forum.id)
        db.session.execute(Forum.__table__.update(Forum.id.in_(ids), values={
            'topic_count': Forum.topic_count -1,
            'post_count': Forum.post_count - self.post_count,
        }))

        db.session.commit()
        old_forum = self.forum
        self.forum = forum
        db.session.commit()
        ids = list(p.id for p in self.forum.parents)
        ids.append(self.forum.id)
        db.session.execute(Forum.__table__.update(Forum.id.in_(ids), values={
            'topic_count': Forum.topic_count + 1,
            'post_count': Forum.post_count + self.post_count,
        }))
        db.session.commit()
        forum.invalidate_topic_cache()
        self.forum.invalidate_topic_cache()
        self.reindex()

        if old_forum.user_count_posts != forum.user_count_posts:
            if forum.user_count_posts and not old_forum.user_count_posts:
                op = operator.add
            elif not forum.user_count_posts and old_forum.user_count_posts:
                op = operator.sub

            db.session.execute(SAUser.__table__.update(
                SAUser.id.in_(db.select([Post.author_id], Post.topic_id == self.id)),
                values={'post_count': op(
                    SAUser.post_count,
                    db.select(
                        [db.func.count()],
                        ((Post.topic_id == self.id) &
                         (Post.author_id == SAUser.id)),
                        Post.__table__)
                    )
                }
            ))
            db.session.commit()

            q = db.select([Post.author_id], Post.topic_id == self.id, distinct=True)
            for x in db.session.execute(q).fetchall():
                cache.delete('portal/user/%d' % x[0])

        # and find a new last post id for the new forum
        new_ids = [p.id for p in self.forum.parents[:-1]]
        new_ids.append(self.forum.id)
        old_ids = [p.id for p in old_forum.parents[:-1]]
        old_ids.append(old_forum.id)

        # search for a new last post in the old and the new forum
        db.session.execute(Forum.__table__.update(Forum.id.in_(new_ids), {
            'last_post_id': db.select([db.func.max(Post.id)], db.and_(
                Topic.id == Post.topic_id,
                Topic.forum_id == Forum.id))
        }))

        db.session.execute(Forum.__table__.update(Forum.id.in_(old_ids), {
            'last_post_id': db.select([db.func.max(Post.id)], db.and_(
                Topic.id == Post.topic_id,
                Topic.forum_id == Forum.id))
        }))


    def get_absolute_url(self, action='show'):
        if action in ('show',):
            return href('forum', 'topic', self.slug)
        if action in ('reply', 'delete', 'hide', 'restore', 'split', 'move',
                      'solve', 'unsolve', 'lock', 'unlock', 'report',
                      'report_done', 'subscribe', 'unsubscribe',
                      'first_unread'):
            return href('forum', 'topic', self.slug, action)

    def get_pagination(self, threshold=3):
        pages = max(0, self.post_count - 1) // POSTS_PER_PAGE + 1
        if pages == 1:
            return u''
        result = []
        ellipsis = u'<span class="ellipsis"> … </span>'
        was_ellipsis = False
        for num in xrange(1, pages + 1):
            if num <= threshold or num > pages - threshold:
                if result and result[-1] != ellipsis:
                    result.append(u'<span class="comma">, </span>')
                link = self.get_absolute_url()
                if num != 1:
                    link = '%s%d/' % (link, num)
                result.append(u'<a href="%s" class="pageselect">%s</a>' %
                              (link, num))
            elif not was_ellipsis:
                was_ellipsis = True
                result.append(ellipsis)
        return u'<span class="pagination">%s</span>' % u''.join(result)

    @property
    def paginated(self):
        return bool((self.post_count - 1) // POSTS_PER_PAGE)

    def get_ubuntu_version(self):
        if self.ubuntu_version:
            return filter(lambda v: v.number == self.ubuntu_version, UBUNTU_VERSIONS)[0]

    def get_version_info(self, default=u'Nicht angegeben'):
        if not (self.ubuntu_version or self.ubuntu_distro):
            return default
        if self.ubuntu_distro == u'keine':
            return u'Kein Ubuntu'
        out = []
        if self.ubuntu_distro:
            out.append(UBUNTU_DISTROS_LEGACY[self.ubuntu_distro])
        if self.ubuntu_version and self.ubuntu_version != u'keine':
            out.append(str(self.get_ubuntu_version()))
        return u' '.join(out)

    def get_read_status(self, user):
        if user.is_anonymous:
            return True
        if not hasattr(user, '_readstatus'):
            user._readstatus = ReadStatus(user.forum_read_status)
        return user._readstatus(self)

    def mark_read(self, user):
        """
        Mark the current topic as read for a given user.
        """
        if user.is_anonymous:
            return
        if not hasattr(user, '_readstatus'):
            user._readstatus = ReadStatus(user.forum_read_status)
        if user._readstatus.mark(self):
            user.forum_read_status = user._readstatus.serialize()

    def reindex(self):
        """Mark the whole topic for reindexing."""
        posts = db.session.query(Post.id).filter(Post.topic_id==self.id)
        for post in posts:
            search.queue('f', post.id)

    def __unicode__(self):
        return self.title

    def __repr__(self):
        return '<%s id=%s title=%s>' % (
            self.__class__.__name__,
            self.id,
            self.title.encode('utf8')
        )


class PostRevision(db.Model):
    """
    This saves old and current revisions of posts. It can be used to restore
    posts if something odd was done to them or to view changes.
    """
    __tablename__ = 'forum_postrevision'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    store_date = db.Column(db.DateTime(timezone=False), nullable=False,
                        default=datetime.utcnow)

    def __repr__(self):
        return '<%s post=%d (%s), stored=%s>' % (
            self.__class__.__name__,
            self.post.id,
            self.post.topic.title,
            self.store_date.strftime('%Y-%m-%d %H:%M')
        )

    def get_absolute_url(self, action='restore'):
        return href('forum', 'revision', self.id, 'restore')

    @property
    def rendered_text(self):
        if self.post.is_plaintext:
            return fix_plaintext(self.text)
        request = current_request._get_current_object()
        context = RenderContext(request, simplified=False)
        return parse(self.text).render(context, 'html')

    def restore(self, request):
        """
        Edits the text of the post the revision belongs to and deletes the
        revision.
        """
        self.post.edit(request, self.text)
        db.session.delete(self)


class Post(db.Model):
    """
    Represents a post in a topic.
    """
    __tablename__ = 'forum_post'
    __mapper_args__ = {'extension': PostMapperExtension()}

    id = db.Column(db.Integer, primary_key=True)
    position = db.Column(db.Integer, nullable=False, default=0, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('portal_user.id'), nullable=False)
    pub_date = db.Column(db.DateTime(timezone=False), nullable=False, index=True,
                      default=datetime.utcnow)
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topic.id'), nullable=False)
    hidden = db.Column(db.Boolean, default=False, nullable=False)
    text = db.Column(db.Text, nullable=False)
    rendered_text = db.Column(db.Text, nullable=True)
    has_revision = db.Column(db.Boolean, default=False, nullable=False)
    is_plaintext = db.Column(db.Boolean, default=False, nullable=False)

    # db.relationship configuration
    author = db.relationship(SAUser,
        primaryjoin=author_id == SAUser.id,
        foreign_keys=[author_id])
    attachments = db.relationship('Attachment', cascade='all, delete')
    revisions = db.relationship(PostRevision, backref='post', lazy='dynamic',
        primaryjoin=PostRevision.post_id == id,
        cascade='all, delete-orphan')

    def render_text(self, request=None, format='html', force_existing=False):
        context = RenderContext(request)
        node = parse(self.text, wiki_force_existing=force_existing)
        return node.render(context, format)

    def get_text(self):
        if self.is_plaintext:
            return fix_plaintext(self.text)
        return self.rendered_text

    def update_search(self):
        """
        This updates the xapian search index.
        """
        search.queue('f', self.id)

    def get_absolute_url(self, action='show'):
        if action == 'show':
            return href('forum', 'post', self.id)
        if action == 'fullurl':
            return Post.url_for_post(self.id)
        return href('forum', 'post', self.id, action)

    @staticmethod
    def url_for_post(id, paramstr=None):
        post = Post.query.get(id)
        if post is None:
            return

        position, slug = post.position, post.topic.slug
        page = max(0, position) // POSTS_PER_PAGE + 1
        url = href('forum', 'topic', slug, *(page != 1 and (page,) or ()))
        return u''.join((url, paramstr and '?%s' % paramstr or '', '#post-%d' % id))

    @staticmethod
    def multi_update_search(ids):
        """
        Updates the search index for quite a lot of posts with a single query.
        """
        SearchQueue.objects.multi_insert('f', ids)

    def edit(self, request, text, is_plaintext=False):
        """
        Change the text of the post. If the post is already stored in the
        database, create a post revision containing the new text.
        If the text has not changed, return.
        """
        if self.text == text and self.is_plaintext == is_plaintext:
            return
        if self.id:
            ## create a first revision for the initial post
            if not self.has_revision:
                rev = PostRevision()
                rev.post = self
                rev.store_date = self.pub_date
                rev.text = self.text
                self.has_revision = True

            ## create a new revision for the current post
            rev = PostRevision()
            rev.post = self
            rev.text = text

        self.text = text
        if not is_plaintext:
            self.rendered_text = self.render_text(request)
        else:
            # cleanup that column so that we save some bytes in the database
            self.rendered_text = None
        self.is_plaintext = is_plaintext

    @property
    def page(self):
        """
        this returns None if page is 1, use post.page or 1 if you need number
        """
        page = self.position // POSTS_PER_PAGE + 1
        if page == 1:
            return None
        return page

    @staticmethod
    def split(posts, old_topic, new_topic):
        """
        This function splits `posts` out of `old_topic` and moves them into
        `new_topic`.
        It is important that `posts` is a list of posts ordered by id
        ascending.
        """
        if len(posts) == old_topic.post_count:
            # The user selected to split all posts out of the topic --> delete
            # the topic.
            remove_topic = True
        else:
            remove_topic = False

        new_topic.post_count += len(posts)
        if not new_topic.last_post_id or \
           posts[-1].id > new_topic.last_post.id:
            new_topic.last_post = posts[-1]
        if not new_topic.first_post_id or \
           posts[0].id < new_topic.first_post.id:
            new_topic.first_post = posts[0]
            new_topic.author = posts[0].author

        ids = [p.id for p in posts]
        db.session.execute(Post.__table__.update(
            Post.id.in_(ids), values={
                'topic_id': new_topic.id
        }))
        db.session.commit()

        connection = db.session.connection()
        connection.execute('''set @rownum:=%s;''', [posts[0].position - 1])
        connection.execute('''
            update forum_post set position=(@rownum:=@rownum+1)
                              where topic_id=%s and position > %s order by id;
        ''', [old_topic.id, posts[0].position])
        connection.execute('''set @rownum:=-1;''')
        connection.execute('''
            update forum_post set position=(@rownum:=@rownum+1)
                              where topic_id=%s order by id;
        ''', [new_topic.id])
        db.session.commit()


        if old_topic.forum.id != new_topic.forum.id:
            # update post count of the forums
            old_topic.forum.post_count -= len(posts)
            new_topic.forum.post_count += len(posts)
            # update last post of the forums
            if not new_topic.forum.last_post or \
               posts[-1].id > new_topic.forum.last_post.id:
                new_topic.forum.last_post = posts[-1]
            if posts[-1].id == old_topic.forum.last_post.id:
                last_post = Post.query.filter(db.and_(
                    Post.topic_id==Topic.id,
                    Topic.forum_id==old_topic.forum_id
                )).first()

                old_topic.forum.last_post_id = last_post and last_post.id \
                                               or None

            o = old_topic.forum.user_count_posts
            n = new_topic.forum.user_count_posts
            if o != n:
                if n and not o:
                    op = operator.add
                elif not n and o:
                    op = operator.sub

                db.session.execute(SAUser.__table__.update(
                    SAUser.id.in_(db.select([Post.author_id], Post.topic_id == old_topic.id)),
                    values={'post_count': op(
                        SAUser.post_count, db.select([db.func.count()],
                            ((Post.topic_id == old_topic.id) &
                             (Post.author_id == SAUser.id)),
                            Post.__table)
                        )
                    }
                ))
                db.session.commit()

                q = db.select([Post.author_id], Post.topic_id == old_topic.id, distinct=True)
                for x in db.session.execute(q).fetchall():
                    cache.delete('portal/user/%d' % x[0])

        db.session.commit()

        if not remove_topic:
            old_topic.post_count -= len(posts)
            if old_topic.last_post.id == posts[-1].id:
                post = Post.query.filter(db.and_(
                    Post.topic_id == old_topic.id,
                    Post.id != old_topic.last_post_id
                )).order_by(Post.id.desc()).first()

                old_topic.last_post = post

            if old_topic.first_post.id == posts[0].id:
                post = Post.query.filter(
                    Topic.id==old_topic.id
                ).order_by(Topic.id.asc()).first()
                old_topic.first_post = post
        else:
            if old_topic.has_poll:
                new_topic.has_poll = True
                db.session.execute(Poll.__table__.update(
                    Topic.id == old_topic.id,
                    {'topic_id': new_topic.id}))
                db.session.commit()
            db.session.delete(old_topic)

        db.session.commit()

        # update the search index which has the post --> topic mapping indexed
        Post.multi_update_search([post.id for post in posts])

        new_topic.forum.invalidate_topic_cache()
        old_topic.forum.invalidate_topic_cache()

    @property
    def grouped_attachments(self):
        def expr(v):
            return u'Bilder' if v.mimetype.startswith('image') and v.mimetype \
                in SUPPORTED_IMAGE_TYPES else u''

        attachments = sorted(self.attachments, key=expr)
        grouped = [(x[0], list(x[1]), u'möglich' in x[0] and 'broken' or '') \
                   for x in groupby(attachments, expr)]
        return grouped

    def check_ownpost_limit(self, type='edit'):
        if type == 'edit':
            if self.topic.last_post_id == self.id:
                t = settings.FORUM_OWNPOST_EDIT_LIMIT[0]
            else:
                t = settings.FORUM_OWNPOST_EDIT_LIMIT[1]
        elif type == 'delete':
            if self.topic.last_post_id == self.id:
                t = settings.FORUM_OWNPOST_DELETE_LIMIT[0]
            else:
                t = settings.FORUM_OWNPOST_DELETE_LIMIT[1]
        else:
            raise KeyError("invalid type: choose one of (edit, delete)")

        if t == 0:
            return False
        if t == -1:
            return True
        delta = datetime.utcnow() - self.pub_date
        return timedelta_to_seconds(delta) < t

    def __unicode__(self):
        return '%s - %s' % (
            self.topic.title,
            self.text[0:20]
        )

    def __repr__(self):
        return '<%s id=%s author=%s>' % (
            self.__class__.__name__,
            self.id,
            self.author
        )


class Attachment(db.Model):
    """
    Represents an attachment associated to a post.
    """
    __tablename__ = 'forum_attachment'

    id = db.Column(db.Integer, primary_key=True)
    file = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    comment = db.Column(db.Text, nullable=True)
    post_id = db.Column(db.Integer, db.ForeignKey('forum_post.id'), nullable=True)
    _mimetype = db.Column('mimetype', db.String(100), nullable=True)

    @staticmethod
    def create(name, content, mime, attachments, override=False, **kwargs):
        """
        This method writes a new attachment bound to a post that is
        not written into the database yet.
        It either returns the new created attachment or None if another
        attachment with that name already exists (and `override` is False).

        :Parameters:
            name
                The file name of the attachment.
            content
                The content of the attachment.
            mime
                The mimetype of the attachment (guess_file is implemented
                as fallback)
            attachments
                A list that includes attachments that are
                already attached to this (not-yet-existing) post.
            override
                Specifies whether other attachments for the same post should
                be overwritten if they have the same name.
        """
        # check whether an attachment with the same name already exists
        existing = filter(lambda a: a.name==name, attachments)
        exists = bool(existing)
        if exists: existing = existing[0]

        if exists and override:
            attachments.remove(existing)
            db.session.delete(existing)
            exists = False

        if not exists:
            # create a temporary filename so we can identify the attachment
            # on binding to the posts
            fn = path.join('forum', 'attachments', 'temp',
                md5((str(time()) + name).encode('utf-8')).hexdigest())
            attachment = Attachment(name=name, file=fn, _mimetype=mime,
                                    **kwargs)
            f = open(path.join(settings.MEDIA_ROOT, fn), 'w')
            try:
                f.write(content)
            finally:
                f.close()
            return attachment

    def delete(self):
        """
        Delete the attachment from the filesystem and
        also mark the database-object for deleting.
        """
        if path.exists(self.filename):
            os.remove(self.filename)
        db.session.delete(self)

    @staticmethod
    def update_post_ids(att_ids, post_id):
        """
        Update the post_id of a few unbound attachments.
        :Parameters:
            att_ids
                A list of the attachment's ids.
            post_id
                The new post id.
        """
        if not att_ids or not post_id:
            return False
        new_path = path.join('forum', 'attachments', str(post_id))
        new_abs_path = path.join(settings.MEDIA_ROOT, new_path)

        if not path.exists(new_abs_path):
            os.mkdir(new_abs_path)

        attachments = db.session.execute(Attachment.__table__.select(db.and_(
            Attachment.id.in_(att_ids),
            Attachment.post_id == None
        ))).fetchall()

        for row in attachments:
            id, old_fn, name, comment, pid, mime = row
            old_fo = open(path.join(settings.MEDIA_ROOT, old_fn), 'r')
            if isinstance(name, unicode):
                name = name.encode('utf-8')
            name = os.path.basename(name)
            name = get_new_unique_filename(name, path=new_abs_path, length=100-len(new_path)-len(os.sep))
            new_fo = open(path.join(new_abs_path, name), 'w')
            try:
                new_fo.write(old_fo.read())
            finally:
                new_fo.close()
                old_fo.close()
            # delete the temp-file
            os.remove(path.join(settings.MEDIA_ROOT, old_fn))
            at = Attachment.__table__
            db.session.execute(at.update(db.and_(
                at.c.id == id,
                at.c.post_id == None
            ), values={'post_id': post_id,
                       at.c.file: '%s/%s'% (new_path, name)}
            ))

    @property
    def size(self):
        """The size of the attachment in bytes."""
        fn = self.filename
        if isinstance(fn, unicode):
            fn = fn.encode('utf-8')
        stat = os.stat(fn)
        return stat.st_size

    @property
    def filename(self):
        """The filename of the attachment on the filesystem."""
        return path.join(settings.MEDIA_ROOT, self.file)

    @property
    def mimetype(self):
        """The mimetype of the attachment."""
        return self._mimetype or guess_type(self.filename)[0] or \
               'application/octet-stream'

    @property
    def contents(self):
        """
        The raw contents of the file.  This is usually unsafe because
        it can cause the memory limit to be reached if the file is too
        big.  However this limitation currently affects the whole django
        system which handles uploads in the memory.
        """
        f = self.open()
        try:
            return f.read()
        finally:
            f.close()

    @property
    def html_representation(self):
        """
        This method returns a `HTML` representation of the attachment for the
        `show_action` page.  If this method does not know about an internal
        representation for the object the return value will be an download
        link to the raw attachment.
        """
        url = escape(self.get_absolute_url())
        show_thumbnails = current_request.user.settings.get(
            'show_thumbnails', False)
        show_preview = current_request.user.settings.get(
            'show_preview', False)

        def isimage():
            """
            This helper returns True if this attachment is a supported image,
            else False.
            """
            return True if self.mimetype in SUPPORTED_IMAGE_TYPES else False

        def istext():
            """
            This helper returns True if this attachment is a text file with
            at most 250 characters, else False.
            """
            return True if self.mimetype.startswith('text/') \
                and len(self.contents) < 250 else False

        def thumbnail():
            """
            This helper returns the thumbnail url of this attachment or None
            if there is no way to create a thumbnail.
            """
            ff = self.file.encode('utf-8')
            img_path = path.join(settings.MEDIA_ROOT,
                'forum/thumbnails/%s-%s' % (self.id, ff.split('/')[-1]))
            if not path.exists(path.abspath(img_path)):
                try:
                    img = Image.open(StringIO(self.contents))
                    if not (img.format == 'PNG' and img.info.get('interlace')) \
                        and img.size > settings.FORUM_THUMBNAIL_SIZE:
                        img.thumbnail(settings.FORUM_THUMBNAIL_SIZE)
                        img.save(img_path, img.format)
                    elif not (img.format == 'PNG' and img.info.get('interlace')) \
                        and img.size < settings.FORUM_THUMBNAIL_SIZE:
                        return url
                    else:
                        return
                except IOError:
                    return
            return href('media', 'forum/thumbnails/%s-%s'
                % (self.id, self.file.split('/')[-1]))

        if show_preview and show_thumbnails and isimage():
            thumb = thumbnail()
            if thumb:
                return u'<a href="%s"><img class="preview" src="%s" ' \
                    u'alt="%s" title="%s"></a>' % (url, thumb, self.comment,
                    self.comment)
            else:
                return u'<a href="%s" type="%s" title="%s">%s ansehen</a>' % (
                    url, self.mimetype, self.comment, self.name)
        elif show_preview and istext():
            return highlight_code(self.contents.decode('utf-8'),
                mimetype=self.mimetype)
        else:
            return u'<a href="%s" type="%s" title="%s">%s herunterladen</a>' % (
                url, self.mimetype, self.comment, self.name)


    def open(self, mode='rb'):
        """
        Open the file as file descriptor.  Don't forget to close this file
        descriptor accordingly.
        """
        return file(self.filename.encode('utf-8'), mode)

    def get_absolute_url(self, action=None):
        return href('media', self.file)


class Privilege(db.Model):
    __tablename__ = 'forum_privilege'
    __mapper_args__ = {'extension': PrivilegeMapperExtension()}

    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('portal_group.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('portal_user.id'), nullable=True)
    forum_id = db.Column(db.Integer, db.ForeignKey('forum_forum.id'), nullable=False)
    positive = db.Column(db.Integer, nullable=True)
    negative = db.Column(db.Integer, nullable=True)

    # db.relationship configuration
    forum = db.relationship(Forum)

    def __init__(self, forum, group=None, user=None, positive=None,
                 negative=None):
        if group is None and user is None:
            raise ValueError('Privilege needs at least one group or user')
        uid = user and user.id or None
        gid = group and group.id or None
        self.group_id = gid
        self.user_id = uid
        self.forum_id = forum.id
        self.positive = positive
        self.negative = negative

    @db.validates('positive', 'negative')
    def validate_postitive(self, key, value):
        """Check that the value is not a - value as this
        would raise nasty bugs in inyoka.forum.acl.  Change values
        to positive integers everytime.
        """
        if value is not None and value < 0:
            return abs(value)
        return value

    def __repr__(self):
        gid, uid = self.group_id, self.user_id
        return '<Privilege(id, %s, fid:%s, %s, %s)' % (
            (self.group_id and 'gid:%s' % gid or 'uid:%s' % uid,
             self.forum_id, self.positive, self.negative))


class PollOption(db.Model):
    __tablename__ = 'forum_polloption'

    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('forum_poll.id'), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    votes = db.Column(db.Integer, default=0, nullable=False)

    @property
    def percentage(self):
        """Calculate the percentage of votes for this poll option."""
        if self.poll.votes:
            return self.votes / self.poll.votes * 100.0
        return 0.0


class PollVote(db.Model):
    __tablename__ = 'forum_voter'

    id = db.Column(db.Integer, primary_key=True)
    voter_id = db.Column(db.Integer, db.ForeignKey('portal_user.id'), nullable=False)
    poll_id = db.Column(db.Integer, db.ForeignKey('forum_poll.id'), nullable=False)


class Poll(db.Model):
    __tablename__ = 'forum_poll'

    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(250), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('forum_topic.id'), nullable=True,
                      index=True)
    start_time = db.Column(db.DateTime(timezone=False), nullable=False,
                        default=datetime.utcnow())
    end_time = db.Column(db.DateTime(timezone=False), nullable=False,
                      default=datetime.utcnow())
    multiple_votes = db.Column(db.Boolean, default=False, nullable=False)

    # relationship configuration
    options = db.relationship(PollOption, backref='poll', cascade='all, delete-orphan')
    votings = db.relationship(PollVote, backref='poll', cascade='all, delete-orphan')

    @staticmethod
    def create(question, options, multiple_votes, topic_id=None,
            time=None):
        now = datetime.utcnow()
        poll = Poll(question=question, multiple_votes=multiple_votes,
                    topic_id=topic_id, start_time=now,
                    end_time=time and now + time or None)
        for option in options:
            option = PollOption(name=option)
            poll.options.append(option)
        return poll

    @staticmethod
    def bind(poll_ids, topic_id):
        """Bind the polls given in poll_ids to the given topic id."""
        if not poll_ids:
            return False
        db.session.execute(Poll.__table__.update(db.and_(
            Poll.id.in_(poll_ids),
            Poll.topic_id == None), values={
                'topic_id': topic_id
        }))

    @property
    def votes(self):
        """Calculate the total number of votes in this poll."""
        return sum(o.votes for o in self.options)

    def has_participated(self, user=None):
        user = user or current_request.user
        return bool(db.session.execute(db.select([1],
            (PollVote.poll_id == self.id) &
            (PollVote.voter_id == user.id))).fetchone())

    participated = property(has_participated)

    @property
    def ended(self):
        """Returns a boolean whether the poll ended already"""
        return self.end_time and datetime.utcnow() > self.end_time

    @deferred
    def can_vote(self):
        """
        Returns a boolean whether the current user can vote in this poll.
        """
        return not self.ended and not self.participated


class WelcomeMessage(db.Model):
    """
    This class can be used, to attach additional Welcome-Messages to
    a category or forum.  That might be usefull for greeting the users or
    explaining extra rules.  The message will be displayed only once for
    each user.
    """
    __tablename__ = 'forum_welcomemessage'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    text = db.Column(db.Text, nullable=False)
    rendered_text = db.Column(db.Text, nullable=False)

    def __init__(self, title, text):
        self.title = title
        self.text = text

    def save(self):
        self.rendered_text = self.render_text()

    def render_text(self, request=None, format='html'):
        if request is None:
            # we have to do that becaus render_text is called during
            # save() which might be triggered outside of a HTTP request
            # eg: converter
            try:
                request = current_request._get_current_object()
            except RuntimeError:
                request = None
        context = RenderContext(request, simplified=True)
        return parse(self.text).render(context, format)


class ReadStatus(object):
    """
    Manages the read status of forums and topics for a specific user.
    """

    def __init__(self, serialized_data):
        self.data = serialized_data and cPickle.loads(str(serialized_data)) or {}

    def __call__(self, item):
        """
        Determine the read status for a forum or topic. If the topic
        was allready read by the user, True is returned.
        """
        forum_id, post_id = None, None
        is_forum = isinstance(item, Forum)
        if is_forum:
            forum_id, post_id = item.id, item.last_post_id
        elif isinstance(item, Topic):
            forum_id, post_id = item.forum_id, item.last_post_id
        else:
            raise ValueError('Can\'t determine read status of an unknown type')
        row = self.data.get(forum_id, (None, []))
        if row[0] >= post_id:
            return True
        elif is_forum:
            return False
        return post_id in row[1]

    def mark(self, item):
        """
        Mark a forum or topic as read. Note that you must save the database
        changes explicitely!
        """
        if self(item):
            return False
        forum_id = isinstance(item, Forum) and item.id or item.forum_id
        post_id = item.last_post_id
        if isinstance(item, Forum):
            self.data[forum_id] = (post_id, set())
            for child in item.children:
                self.mark(child)
            if item.parent_id and reduce(lambda a, b: a and b, \
                [self(c) for c in item.parent.children], True):
                self.mark(item.parent)
            return True
        row = self.data.get(forum_id, (None, set()))
        row[1].add(post_id)
        if reduce(lambda a, b: a and b,
            [self(c) for c in item.forum.children], True) and not \
            db.session.execute(db.select([1], db.and_(Forum.id == forum_id,
                Forum.last_post_id > (row[0] or -1),
                ~Forum.last_post_id.in_(row[1]))).limit(1)).fetchone():
            self.mark(item.forum)
            return True
        elif len(row[1]) > settings.FORUM_LIMIT_UNREAD:
            r = list(row[1])
            r.sort()
            row = (r[settings.FORUM_LIMIT_UNREAD//2],
                set(r[settings.FORUM_LIMIT_UNREAD//2:]))
        self.data[forum_id] = row
        return True

    def serialize(self):
        return cPickle.dumps(self.data)


# Circular imports
from inyoka.wiki.parser import parse, RenderContext
from inyoka.portal.models import SearchQueue
