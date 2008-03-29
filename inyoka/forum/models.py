# -*- coding: utf-8 -*-
"""
    inyoka.forum.models
    ~~~~~~~~~~~~~~~~~~~

    Database models for the forum.

    :copyright: 2007 by Benjamin Wiegand, Armin Ronacher, Christoph Hack.
    :license: GNU GPL, see LICENSE for more details.
"""
from __future__ import division
import re
import random
import cPickle
from mimetypes import guess_type
from datetime import datetime
from sqlalchemy.orm import eagerload, relation, backref, MapperExtension, \
        EXT_CONTINUE
from sqlalchemy.sql import select, func, and_, not_, exists
from inyoka.conf import settings
from inyoka.ikhaya.models import Article
from inyoka.wiki.parser import parse, render, RenderContext
from inyoka.utils.text import slugify
from inyoka.utils.html import escape
from inyoka.utils.urls import href
from inyoka.utils.highlight import highlight_code
from inyoka.utils.search import search
from inyoka.utils.cache import cache
from inyoka.utils.local import current_request
from inyoka.utils.database import session as dbsession
from inyoka.forum.database import forum_table, topic_table, post_table, \
        user_table, attachment_table, poll_table, privilege_table, \
        poll_option_table, poll_vote_table
from inyoka.portal.user import User, Group


POSTS_PER_PAGE = 15
TOPICS_PER_PAGE = 30
UBUNTU_VERSIONS = {
    '4.10': '4.10 (Warty Warthog)',
    '5.04': '5.04 (Hoary Hedgehog)',
    '5.10': '5.10 (Breezy Badger)',
    '6.06': '6.06 (Dapper Drake)',
    '6.10': '6.10 (Edgy Eft)',
    '7.04': '7.04 (Feisty Fawn)',
    '7.10': '7.10 (Gutsy Gibbon)',
    '8.04': '8.04 (Hardy Heron)'
}
UBUNTU_DISTROS = {
    'ubuntu': 'Ubuntu',
    'kubuntu': 'Kubuntu',
    'xubuntu': 'Xubuntu',
    'edubuntu': 'Edubuntu',
    'server': 'Server',
}
REGEX = '(.+)Ubuntu\/%s \(%s\)(.+)'
VERSION_REGEXES = [
    (i, re.compile(REGEX % (i, name.split(' ')[0].lower())))
    for i, name in UBUNTU_VERSIONS.iteritems()
]


def get_ubuntu_version(request):
    """
    Try to find out which ubuntu version the user is using by matching the
    HTTP_USER_AGGENT against some regexes.
    """
    for i, regex in VERSION_REGEXES:
        if regex.match(request.META.get('HTTP_USER_AGENT', '')):
            return i


class SearchMapperExtension(MapperExtension):
    """
    Simple MapperExtension that listen on some events
    to get the xapian database up to date.
    """
    def after_delete(self, mapper, connection, instance):
        search.queue('f', instance.id)


class ForumMapperExtension(MapperExtension):

    def get(self, query, ident, *args, **kwargs):
        if isinstance(ident, basestring):
            slug_map = cache.get('forum/slugs')
            if slug_map is None:
                slug_map = dict(dbsession.execute(select(
                    [forum_table.c.slug, forum_table.c.id])).fetchall())
                cache.set('forum/slugs', slug_map)
            ident = slug_map.get(ident)
            if ident is None:
                return None
        key = query.mapper.identity_key_from_primary_key(ident)
        cache_key = 'forum/forum/%d' % int(key[1][0])
        forum = cache.get(cache_key)
        if not forum:
            forum = query.options(eagerload('last_post'), \
                eagerload('last_post.author'))._get(key, ident, **kwargs)
            cache.set(cache_key, forum)
        else:
            forum = query.session.merge(forum, dont_load=True)
        return forum

    def before_insert(self, mapper, connection, instance):
        if not instance.slug:
            instance.slug = slugify(instance.name)

    def after_update(self, mapper, connection, instance):
        cache.delete('forum/forum/%d' % instance.id)


class TopicMapperExtension(MapperExtension):

    def before_insert(self, mapper, connection, instance):
        if not instance.forum and instance.forum_id:
            instance.forum = Forum.query.get(instance.forum_id)
        if not instance.forum or instance.forum.parent_id is None:
            raise ValueError('Invalid Forum')
        # shorten slug to 45 chars (max length is 50) because else problems
        # when appending id can occur
        instance.slug = slugify(instance.title)[:45]
        if Topic.query.filter_by(slug=instance.slug).first():
            slugs = connection.execute(select([topic_table.c.slug],
                topic_table.c.slug.like('%s-%%' % instance.slug)))
            start = len(instance.slug) + 1
            try:
                instance.slug += '-%d' % (max(int(s[0][start:]) for s in slugs \
                    if s[0][start:].isdigit()) + 1)
            except ValueError:
                instance.slug += '-1'

    def after_insert(self, mapper, connection, instance):
        parent_ids = list(p.id for p in instance.forum.parents)
        parent_ids.append(instance.forum_id)
        connection.execute(forum_table.update(
            forum_table.c.id.in_(parent_ids), values={
            'topic_count': forum_table.c.post_count + 1,
        }))

    def before_delete(self, mapper, connection, instance):
        self.deregister(mapper, connection, instance)
        connection.execute(forum_table.update(
            forum_table.c.last_post_id.in_(select([post_table.c.id],
                post_table.c.topic_id == instance.id)), values={
            'last_post_id': None
        }))
        connection.execute(topic_table.update(
            topic_table.c.id == instance.id, values={
            'last_post_id': None,
            'first_post_id': None
        }))
        connection.execute(post_table.delete(
            post_table.c.topic_id == instance.id
        ))

    def deregister(self, mapper, connection, instance):
        """Remove references and decrement post counts for this topic."""
        def collect_children_ids(forum, children):
            for child in forum.children:
                children.append(child.id)
                collect_children_ids(child, children)
        if not instance.forum:
            return
        forums = instance.forum.parents
        forums.append(instance.forum)
        for forum in forums:
            forum.topic_count = forum_table.c.topic_count - 1
            forum.post_count = forum_table.c.post_count - instance.post_count
            if forum.last_post_id == instance.last_post_id:
                children = []
                collect_children_ids(forum, children)
                forum.last_post_id = select([func.max(post_table.c.id)], and_(
                    post_table.c.topic_id != instance.id,
                    topic_table.c.forum_id.in_(children),
                    topic_table.c.id == post_table.c.topic_id))


class PostMapperExtension(MapperExtension):

    def before_insert(self, mapper, connection, instance):
        instance.rendered_text = instance.render_text()
        if not instance.pub_date:
            instance.pub_date = datetime.utcnow()

    def after_insert(self, mapper, connection, instance):
        connection.execute(user_table.update(
            user_table.c.id==instance.author_id, values={
            'post_count': user_table.c.post_count + 1
        }))
        cache.delete('portal/user/%d' % instance.author_id)
        values = {
            'post_count': topic_table.c.post_count + 1,
            'last_post_id': instance.id
        }
        if instance.topic.first_post_id is None:
            values['first_post_id'] = instance.id
        connection.execute(topic_table.update(
            topic_table.c.id==instance.topic_id, values=values))
        parent_ids = list(p.id for p in instance.topic.forum.parents)
        parent_ids.append(instance.topic.forum_id)
        connection.execute(forum_table.update(
            forum_table.c.id.in_(parent_ids), values={
            'post_count': forum_table.c.post_count + 1,
            'last_post_id': instance.id
        }))
        for page in xrange(1, 5):
            cache.delete('forum/topics/%d/%d' % (instance.topic.forum_id,
                page))
        search.queue('f', instance.id)

    def unregister(self, mapper, connection, instance):
        forums = instance.topic.forum.parents
        forums.append(instance.topic.forum)
        parent_ids.append(instance.topic.forum_id)
        connection.ex

    def before_delete(self, mapper, connection, instance):
        # TODO: unregister
        pass


class Forum(object):
    """
    This is a forum that may contain subforums or threads.
    If parent is None this forum is a root forum, else it's a subforum.
    Position is an integer that's used to sort the forums.  The lower position
    is, the higher the forum is displayed.
    """

    def get_absolute_url(self, action='show'):
        return href(*{
            'show': ('forum', self.parent_id and 'forum' or 'category',
                     self.slug),
            'newtopic': ('forum', 'forum', self.slug, 'newtopic'),
            'welcome': ('forum', 'forum', self.slug, 'welcome'),
            'subscribe': ('forum', 'forum', self.slug, 'subscribe'),
            'unsubscribe': ('forum', 'forum', self.slug, 'unsubscribe'),
            'edit': ('admin', 'forum', 'edit', self.id)
        }[action])

    @property
    def parents(self):
        """Return a list of all parent forums up to the root level."""
        parents = []
        forum = self
        while forum.parent_id:
            forum = forum.parent
            parents.append(forum)
        return parents

    @property
    def children(self):
        cache_key = 'forum/children/%d' % self.id
        children_ids = cache.get(cache_key)
        if children_ids is None:
            children_ids = [row[0] for row in dbsession.execute(select(
                [forum_table.c.id], forum_table.c.parent_id == self.id)) \
                .fetchall()]
            cache.set(cache_key, children_ids)
        children = [Forum.query.get(id) for id in children_ids]
        return children

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
            topics = Topic.query.options(eagerload('author'), eagerload('last_post'),
                eagerload('last_post.author')).filter_by(forum_id=self.id) \
                .order_by((Topic.sticky.desc(), Topic.last_post_id.desc())).limit(limit)
            if limit == settings.FORUM_TOPIC_CACHE:
                topics = topics.all()
                cache.set(key, topics)

        return (count < limit) and topics[:count] or topics

    latest_topics = property(get_latest_topics)

    def get_read_status(self, user):
        """
        Determine the read status of the whole forum for a specific
        user.
        """
        if user.is_anonymous:
            return True
        if not hasattr(user, '_readstatus'):
            user._readstatus = ReadStatus(user.forum_read_status)
        return user._readstatus(self)

    def mark_read(self, user):
        """
        Mark all topics in this forum and all related subforums as
        read for the specificed user.
        """
        if user.is_anonymous:
            return
        if not hasattr(user, '_readstatus'):
            user._readstatus = ReadStatus(user.forum_read_status)
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
        dbsession.flush(user)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return '<%s id=%s slug=%s name=%s>' % (
            self.__class__.__name__,
            self.id,
            self.slug.encode('utf-8'),
            self.name.encode('utf-8')
        )


class Topic(object):
    """
    A topic symbolizes a bunch of Posts (at least one) that is located inside
    a Forum.
    When creating a new topic, a new post is added to it automatically.
    """

    def touch(self):
        """Increment the view count in a safe way."""
        self.view_count = topic_table.c.view_count + 1

    def move(self, forum):
        """Move the topic to an other forum."""
        ids = list(p.id for p in self.forum.parents)
        ids.append(self.forum.id)
        dbsession.execute(forum_table.update(forum_table.c.id.in_(ids), values={
            'topic_count': forum_table.c.topic_count - 1,
            'post_count': topic_table.select([func.count(topic_table.c.id)],
                    topic_table.c.id == self.id) - 1,
        }))
        topic.forum = forum
        dbsession.flush(self)
        ids = list(p.id for p in self.forum.parents)
        ids.append(self.forum.id)
        dbsession.execute(forum_table.update(forum_table.c.id.in_(ids), values={
            'topic_count': forum_table.c.topic_count + 1,
            'post_count': topic_table.select([func.count(topic_table.c.id)],
                    topic_table.c.id == self.id) - 1,
        }))

    def get_absolute_url(self, action='show'):
        if action == 'show':
            return href('forum', 'topic', self.slug)
        return href('forum', 'topic', self.slug, action)


    def register(self):
        self.forum.post_count += self.post_count
        self.forum.topic_count += 1

        if not self.forum.last_post or self.last_post.id > \
                                        self.forum.last_post.id:
            self.forum.last_post = self.last_post
        self.forum.save()

    def deregister(self):
        self.forum.post_count -= self.post_count
        self.forum.topic_count -= 1
        if self.last_post_id == self.forum.last_post.id:
            try:
                last_topic = self.forum.topic_set.exclude(id=self.id) \
                                                 .order_by('-last_post_id')[0]
                self.forum.last_post = last_topic.last_post
            except IndexError:
                self.forum.last_post = None

        self.forum.save()

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
                was_space = False
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
        return bool(self.post_count // POSTS_PER_PAGE)

    def get_ubuntu_version(self):
        if not (self.ubuntu_version or self.ubuntu_distro):
            return u'Nicht angegeben'
        out = []
        if self.ubuntu_distro:
            out.append(UBUNTU_DISTROS[self.ubuntu_distro])
        if self.ubuntu_version:
            out.append(u'%s (%s)' % (UBUNTU_VERSIONS[self.ubuntu_version],
                                    self.ubuntu_version))
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

    def __unicode__(self):
        return self.title

    def __repr__(self):
        return '<%s id=%s title=%s>' % (
            self.__class__.__name__,
            self.id,
            self.title.encode('utf8')
        )


class Post(object):
    """
    Represents a post in a topic.
    """

    def render_text(self, request=None, format='html', nocache=False,
                    force_existing=False):
        if request is None:
            # we have to do that becaus render_text is called during
            # save() which might be triggered outside of a HTTP request
            # eg: converter
            try:
                request = current_request._get_current_object()
            except RuntimeError:
                request = None
        context = RenderContext(request, simplified=True)
        if nocache or self.id is None or format != 'html':
            node = parse(self.text, wiki_force_existing=force_existing)
            return node.render(context, format)
        key = 'forum/post/%s' % self.id
        instructions = cache.get(key)
        if instructions is None:
            node = parse(self.text, wiki_force_existing=force_existing)
            instructions = node.compile(format)
            cache.set(key, instructions)
        return render(instructions, context)

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
        row = dbsession.execute(select(
            [func.count(post_table.c.id), topic_table.c.slug], and_(
                topic_table.c.id == post_table.c.topic_id,
                topic_table.c.id == select(
                    [post_table.c.topic_id], post_table.c.id == id),
                    post_table.c.id <= id)
            ).group_by(topic_table.c.id)).fetchone()
        if not row:
            return None
        post_count, slug = row
        page = max(0, post_count - 1) // POSTS_PER_PAGE + 1
        return ''.join((href('forum', 'topic', slug,
            *(page != 1 and (page,) or ())),
            paramstr and '?%s' % paramstr or '', '#post-%d' % id))

    @staticmethod
    def get_max_id():
        return dbsession.execute(select([func.max(Post.c.id)])).fetchone()[0]

    def deregister(self):
        """
        This function removes all relations to this post.
        """
        pt, tt = post_table, topic_table
        if self.id == self.topic.last_post_id:
            try:
                self.topic.last_post = Post.query.filter(and_(
                    pt.c.topic_id==self.topic.id,
                    not_(pt.c.id==self.id)
                )).order_by(pt.c.id)[0]
            except IndexError:
                self.topic.last_post = None
        if self.id == self.topic.forum.last_post_id:
            last_post = Post.query.filter(and_(
                pt.c.topic_id==tt.c.id,
                tt.c.forum_id==self.topic.forum.id,
                pt.c.id!=self.id
            )).order_by(pt.c.id.desc()).limit(1)[0]
            try:
                self.topic.forum.last_post = last_post
            except TypeError:
                self.topic.forum.last_post = None
        self.topic.post_count -= 1
        dbsession.commit()
        for idx in xrange(1, 5):
            cache.delete('forum/topics/%d/%d' % (self.topic.id, idx))

    @staticmethod
    def split(posts, forum_id=None, title=None, topic_slug=None):
        posts = list(posts)
        old_topic = posts[0].topic

        if len(posts) == old_topic.post_count:
            # The user selected to split all posts out of the topic --> delete
            # the topic.
            remove_topic = True
        else:
            remove_topic = False

        if forum_id and title:
            action = 'new'
        elif topic_slug:
            action = 'add'
        else:
            return None

        if action == 'new':
            t = Topic(
                title=title,
                author=posts[0].author,
                last_post=posts[-1],
                forum_id=forum_id,
                slug=None,
                post_count=len(posts)
            )
            dbsession.flush()
            t.forum.topic_count += 1
        else:
            t = Topic.query.filter_by(slug=topic_slug).first()
            t.post_count += len(posts)
            if posts[-1].id > t.last_post.id:
                t.last_post = posts[-1]
            if posts[0].id < t.first_post.id:
                t.first_post = posts[0]
                t.author = posts[0].author

        dbsession.flush()
        ids = [p.id for p in posts]
        dbsession.execute(post_table.update(
            post_table.c.id.in_(ids), values={
                'topic_id': t.id
        }))
        dbsession.commit()

        if old_topic.forum.id != t.forum.id:
            # update post count of the forums
            old_topic.forum.post_count -= len(posts)
            t.forum.post_count += len(posts)
            # update last post of the forums
            if not t.forum.last_post or posts[-1].id > t.forum.last_post.id:
                t.forum.last_post = posts[-1]
            if posts[-1].id == old_topic.forum.last_post.id:
                last_post = Post.query.filter(and_(
                    post_table.c.topic_id==topic_table.c.id,
                    topic_table.c.forum_id==old_topic.forum_id
                )).first()

                old_topic.forum.last_post_id = last_post and last_post.id \
                                               or None

        dbsession.commit()

        if not remove_topic:
            old_topic.post_count -= len(posts)
            if old_topic.last_post.id == posts[-1].id:
                post = Post.query.filter(
                    topic_table.c.id==old_topic.id
                ).order_by(topic_table.c.id.desc()).first()
                old_topic.last_post = post
            if old_topic.first_post.id == posts[0].id:
                post = Post.query.filter(
                    topic_table.c.id==old_topic.id
                ).order_by(topic_table.c.id.asc()).first()
                old_topic.first_post = post
        else:
            dbsession.delete(old_topic)

        dbsession.commit()

        # update the search index which has the post --> topic mapping indexed
        for post in posts:
            post.topic = t
            post.update_search()

        return t

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



class PostRevision(object):
    """
    This saves old revisions of posts. It can be used to restore posts if
    something odd was done to them.
    """
    #post = models.ForeignKey(Post, verbose_name='zugehöriges Posting')
    #text = models.TextField('Text')
    #store_date = models.DateTimeField('Datum der Löschung')

    def __repr__(self):
        return '<%s post=%d (%s), stored=%s>' % (
            self.__class__.__name__,
            self.post.id,
            self.post.topic.title,
            self.store_date.strftime('%Y-%m-%d %H:%M')
        )


class Attachment(object):
    """
    Posts can have uploaded data associated, this table holds the  mapping
    to the uploaded file on the file system.
    It has these fields:
    `file`
        The path to the attachment itself.
    `name`
        The name of the attachment.
    `comment`
        The comment of the attachment.
    `post`
        The post the attachment belongs to.  It may be NULL if the attachment
        belongs to a post that is not yet created.
    """
    #objects = AttachmentManager()
    #file = models.FileField(upload_to='forum/attachments/%S/%W')
    #name = models.CharField(max_length=255)
    #comment = models.TextField()
    #post = models.ForeignKey(Post, null=True)

    @property
    def size(self):
        """The size of the attachment in bytes."""
        return self.get_file_size()

    @property
    def filename(self):
        """The filename of the attachment on the filesystem."""
        return self.get_file_filename()

    @property
    def mimetype(self):
        """The mimetype of the attachment."""
        return guess_type(self.get_file_filename())[0] or \
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
        if self.mimetype.startswith('image/'):
            return u'<a href="%s"><img class="attachment" src="%s" ' \
                   u'alt="%s"></a>' % ((url,) * 3)
        elif self.mimetype.startswith('text/'):
            return highlight_code(self.contents, filename=self.filename)
        else:
            return u'<a href="%s">Anhang herunterladen</a>' % url

    def open(self, mode='rb'):
        """
        Open the file as file descriptor.  Don't forget to close this file
        descriptor accordingly.
        """
        return file(self.get_file_filename(), mode)

    def get_absolute_url(self):
        return self.get_file_url()


class Privilege(object):

    def __init__(self, forum, group=None, user=None, **kwargs):
        if group is None and user is None:
            raise ValueError('Privilege needs at least one group or user')
        uid = user and user.id or None
        gid = group and group.id or None
        self.group_id = gid
        self.user_id = uid
        self.forum_id = forum.id
        for permission, value in kwargs.iteritems():
            setattr(self, permission, value)


class Poll(object):

    def __init__(self, question, options, multiple_votes):
        self.start_time = datetime.utcnow()
        self.question = question
        for option in options:
            if not isinstance(option, PollOption):
                option = PollOption(name=option)
            self.options.append(option)
        self.multiple_votes = multiple_votes

    @staticmethod
    def bind(poll_ids, topic_id):
        """Bind the polls given in poll_ids to the given topic id."""
        if not poll_ids:
            return False
        dbsession.execute(poll_table.update(and_(poll_table.c.id.in_(poll_ids),
            poll_table.c.topic_id == None), values={
                'topic_id': topic_id
        }))

    @property
    def votes(self):
        """Calculate the total number of votes in this poll."""
        return sum(o.votes for o in self.options)

    def has_participated(self, user=None):
        user = user or current_request.user
        return dbsession.execute(select([exists([PollVote.c.id],
            and_(PollVote.c.id == self.id,
            PollVote.c.voter_id == user.id))])).fetchone()[0]

    participated = property(has_participated)


class PollOption(object):

    @property
    def percentage(self):
        """Calculate the percentage of votes for this poll option."""
        return int(round(self.votes / self.poll.votes * 100))


class PollVote(object):
    pass


class WelcomeMessage(object):
    """
    This class can be used, to attach additional Welcome-Messages to
    a category or forum.  That might be usefull for greeting the users or
    explaining extra rules.  The message will be displayed only once for
    each user.
    """
    #title = models.CharField(max_length=120)
    #text = models.TextField('Nachricht')
    #rendered_text = models.TextField('Gerenderte Nachricht')

    def save(self):
        self.rendered_text = self.render_text()
        super(WelcomeMessage, self).save()

    def render_text(self, request=None, format='html'):
        if request is None:
            request = request._get_current_object()
        context = RenderContext(request, simplified=True)
        return parse(self.text).render(context, format)


# set up the mappers for sqlalchemy
class SAUser(object):

    def get_absolute_url(self):
        return href('portal', 'users', self.username)

    def __unicode__(self):
        return self.username


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
        print 'MARK', item, self.data
        forum_id = isinstance(item, Forum) and item.id or item.forum_id
        post_id = item.last_post_id
        if isinstance(item, Forum):
            self.data[forum_id] = (post_id, set())
            for child in item.children:
                self.mark(child)
            if item.parent_id and reduce(lambda a, b: a and b, \
                [self(c) for c in item.parent.children]):
                self.mark(item.parent)
            print ' FORUM', self.data
            return True
        row = self.data.get(forum_id, (None, set()))
        row[1].add(post_id)
        all = True
        for child in item.forum.children:
            all = all and self(child)
        if reduce(lambda a, b: a and b,
            [self(c) for c in item.forum.children]) and not \
            dbsession.execute(select([1], and_(forum_table.c.id == forum_id,
            forum_table.c.last_post_id > (row[0] or -1),
            ~forum_table.c.last_post_id.in_(row[1]))).limit(1)).fetchone():
            self.mark(item.forum)
            print ' ALL', self.data
            return True
        elif len(row[1]) > settings.FORUM_LIMIT_UNREAD:
            r = list(row[1])
            r.sort()
            row[1] = set(r[settings.FORUM_LIMIT_UNREAD//2:])
            row[0] = r[settings.FORUM_LIMIT_UNREAD//2]
            print ' TRUNCATED'
        self.data[forum_id] = row
        print ' RESULT', self.data
        return True

    def serialize(self):
        return cPickle.dumps(self.data)


dbsession.mapper(SAUser, user_table)
dbsession.mapper(Privilege, privilege_table, properties={
    'forum': relation(Forum)
})
dbsession.mapper(Forum, forum_table, properties={
    'topics': relation(Topic),
    '_children': relation(Forum, backref=backref('parent',
        remote_side=[forum_table.c.id])),
    'last_post': relation(Post)},
    extension=ForumMapperExtension()
)
dbsession.mapper(Topic, topic_table, properties={
    'author': relation(SAUser,
        primaryjoin=topic_table.c.author_id == user_table.c.id,
        foreign_keys=[topic_table.c.author_id]),
    'reporter': relation(SAUser,
        primaryjoin=topic_table.c.reporter_id == user_table.c.id,
        foreign_keys=[topic_table.c.reporter_id]),
    'last_post': relation(Post,
        primaryjoin=topic_table.c.last_post_id == post_table.c.id),
    'first_post': relation(Post,
        primaryjoin=topic_table.c.first_post_id == post_table.c.id),
    'forum': relation(Forum),
    'posts': relation(Post, backref='topic',
        primaryjoin=topic_table.c.id == post_table.c.topic_id)
    }, extension=TopicMapperExtension()
)
dbsession.mapper(Post, post_table, properties={
    'author': relation(SAUser,
        primaryjoin=post_table.c.author_id == user_table.c.id,
        foreign_keys=[post_table.c.author_id]),
    'attachments': relation(Attachment)},
    extension=PostMapperExtension()
)
dbsession.mapper(Attachment, attachment_table)
dbsession.mapper(Poll, poll_table, properties={
    'topic': relation(Topic, backref='polls'),
    'options': relation(PollOption)
})
dbsession.mapper(PollOption, poll_option_table, properties={
    'poll': relation(Poll)
})
dbsession.mapper(PollVote, poll_vote_table, properties={
    'poll': relation(Poll)
})
