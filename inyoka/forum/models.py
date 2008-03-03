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
from django.db import models, connection
from mimetypes import guess_type
from datetime import datetime
from django.utils.html import escape
from django.core.cache import cache
from django.conf import settings
from inyoka.ikhaya.models import Article
from inyoka.wiki.parser import parse, render, RenderContext
from inyoka.utils import slugify
from inyoka.utils.urls import href, url_for
from inyoka.utils.highlight import highlight_code
from inyoka.utils.search import search
from inyoka.middlewares.registry import r
from inyoka.portal.user import User, Group


POSTS_PER_PAGE = 10
UBUNTU_VERSIONS = {
    '4.10': 'Warty Warthog',
    '5.04': 'Hoary Hedgehog',
    '5.10': 'Breezy Badger',
    '6.06': 'Dapper Drake',
    '6.10': 'Edgy Eft',
    '7.04': 'Feisty Fawn',
    '7.10': 'Gutsy Gibbon',
    '8.04': 'Hardy Heron'
}
UBUNTU_DISTROS = {
    'ubuntu': 'Ubuntu',
    'kubuntu': 'Kubuntu',
    'xubuntu': 'Xubuntu',
    'edubuntu': 'Edubuntu'
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


class ForumManager(models.Manager):
    """
    Manager class for easier forum access.
    """

    def get_categories(self, depth=None):
        """
        Returns all forum objects that are categories (parent = None).
        If depth is an integer, it also fetches the categories' subforums
        recursively until depth.
        """
        o = Forum.objects
        if depth:
            o = o.select_related(depth=depth)

        return o.filter(parent__isnull=True)

    def get_forums(self):
        """
        Return all the forum objects that aren't catecories (parent != None).
        """
        return Forum.objects.filter(parent__isnull=False)

    def get_forum_structure(self):
        """
        Fetch the whole forum structure, build up the tree and cache everything.
        """
        struct = cache.get('forum/structure')
        if struct:
            return struct
        forums = list(Forum.objects.all())
        struct = {}
        for forum in forums:
            struct[forum.id] = { 'forum': forum }
        for forum in forums:
            children = [(c.position, c.id) for c in forums \
                        if c.parent_id == forum.id]
            children.sort()
            children = [c[1] for c in children]
            struct[forum.id]['children'] = children
            parents = []
            parent = forum.parent_id
            while parent:
                parents.append(parent)
                parent = struct.get(parent)
                parent = parent and parent['forum'].parent_id
            parents.reverse()
            struct[forum.id]['parents'] = parents
        cache.set('forum/structure', struct, 10*60000)
        return struct


class TopicManager(models.Manager):
    """
    Manager class for the `Topic` model.
    """

    def create(self, forum, title, text, author=None, pub_date=None, has_poll=
               False, slug=None, ubuntu_version=None, ubuntu_distro=None,
               sticky=False):
        author = author or r.request.user
        pub_date = pub_date or datetime.utcnow()
        topic = Topic(title=title, forum=forum, slug=slug, view_count=0,
                      author=author, ubuntu_distro=ubuntu_distro,
                      ubuntu_version=ubuntu_version, has_poll=has_poll,
                      post_count=1, sticky=sticky)
        topic.save()
        post = Post(text=text, author=author, pub_date=pub_date, topic=topic)
        post.save()
        topic.last_post = post
        topic.first_post = post
        topic.forum.last_post = post
        topic.forum.save()
        for parent in topic.forum.parents:
            parent.last_post = post
            parent.save()
        topic.register()
        topic.save()
        return topic

    def by_forum(self, forum_id):
        """
        Return a django query object with all threads inside a forum.
        Topics that are sticky are placed at the beginning.  The remaining
        ones are ordered by last_post.
        """
        return Topic.objects.filter(forum__id=forum_id)

    def move(self, topic, new_forum):
        """
        Move `topic` to `new_forum` and update post count and last post.
        """
        topic.deregister()
        topic.forum = new_forum
        topic.register()
        topic.save()
        return topic

    def mark_as_done(self, topic_ids):
        """
        This function removes the "reported" flag of a bunch of topics.
        """
        cur = connection.cursor()
        cur.execute('''
            update forum_topic
                set reported = NULL,
                    reporter_id = NULL
             where id in (%s)
        ''' % ', '.join(('%s',) * len(topic_ids)), topic_ids)
        cur.close()
        connection._commit()
        cache.delete('forum/reported_topic_count')


class PostManager(models.Manager):
    """
    The manager for posts.
    """

    def get_post_topic(self, post_id):
        """
        Return a tuple with the topic slug and page as well as the anchor.
        """
        cur = connection.cursor()
        cur.execute('''
            select count(p.id), t.slug
              from forum_post p,
                   forum_post p2,
                   forum_topic t
             where p.topic_id = t.id and
                   p.topic_id = p2.topic_id and
                   p.id <= p2.id and
                   p2.id = %s
          group by t.id;
        ''', (post_id,))
        row = cur.fetchone()
        if row is not None:
            post_count, slug = row
            page = post_count // POSTS_PER_PAGE + 1
            return (slug, page, str(post_id))

    def split(self, posts, forum_id=None, title=None, topic_slug=None):
        """
        This splits a topic and either adds the splitted posts to a new or to
        an existing topic.

        :Parameters:
            posts
                A queryset of posts that are all children of the old topic and
                should be moved out of it.
            forum_id
                The id of the forum the new topic should belong to.
            title
                The title of the new topic.
            topic_slug
                The slug of the existing topic the posts should belong to.
        """
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
            t.forum.topic_count += 1
        else:
            t = Topic.objects.get(slug=topic_slug)
            t.post_count = t.post_count + len(posts)
            if posts[-1].id > t.last_post.id:
                t.last_post = posts[-1]
            if posts[0].id < t.first_post.id:
                t.first_post = posts[0]
                t.author = posts[0].author

        t.save()

        cur = connection.cursor()
        cur.execute('''
            update forum_post
                set topic_id = %%s
             where id in (%s)
        ''' % ', '.join(('%s',) * len(posts)),
            (t.id,) + tuple(p.id for p in posts))
        cur.close()
        connection._commit()

        if old_topic.forum.id != t.forum.id:
            # update post count of the forums
            old_topic.forum.post_count -= len(posts)
            t.forum.post_count += len(posts)
            # update last post of the forums
            if not t.forum.last_post or posts[-1].id > t.forum.last_post.id:
                t.forum.last_post = posts[-1]
            if posts[-1].id == old_topic.forum.last_post.id:
                cur = connection.cursor()
                cur.execute('''
                    select p.id
                     from forum_post p, forum_topic t, forum_forum f
                     where p.topic_id = t.id and
                           t.forum_id = %s
                     order by id desc
                     limit 1
                ''', [old_topic.forum.id])
                try:
                    old_topic.forum.last_post_id = cur.fetchone()[0]
                except TypeError:
                    old_topic.forum.last_post = None

        t.save()
        t.forum.save()

        if not remove_topic:
            old_topic.post_count-= len(posts)
            old_topic.last_post = Post.objects.filter(topic__id=old_topic.id)\
                                              .order_by('-id')[0]
            if old_topic.first_post.id == posts[0].id:
                old_topic.first_post = Post.objects.order_by('id') \
                                           .filter(topic__id=old_topic.id)[0]
            old_topic.save()
        else:
            old_topic.delete()
        old_topic.forum.save()

        # update the search index which has the post --> topic mapping indexed
        for post in posts:
            post.topic = t
            post.update_search()

        return t

    def get_max_id(self):
        cur = connection.cursor()
        cur.execute('''
            select max(p.id)
              from forum_post p;
        ''')
        row = cur.fetchone()
        return row and row[0] or 0

    def get_new_posts(self):
        """
        Fetch the latest topics (cached).
        """
        posts = cache.get('forum/newposts')
        if posts is not None:
            return posts
        cur = connection.cursor()
        cur.execute('''
            select p.id
              from forum_topic t, forum_post p
             where p.id = t.last_post_id
          order by p.pub_date desc
             limit 1000
        ''')
        posts = []
        for row in cur.fetchall():
            posts.append(Post.objects.select_related().get(id__exact=row[0]))
        cache.set('forum/newposts', posts, 30)
        return posts


class AttachmentManager(models.Manager):
    """
    Manager class for the `Attachment` model.
    """

    def create(self, name, content, attachments, override=False):
        """
        This function writes a new attachment for a post that is not yet
        written into the database.
        It either returns the new created attachment or None if another
        attachment with the same name already existed (and wasn't overwritten)
        :Parameters:
            name
                The file name of the attachment.
            content
                The content of the attachment.
            attachments
                A list of attachments that are already attached to this
                not-yet-existing post.
            override
                Specifies whether other attachments for the same post should
                be overwritten if they have the same name.
        """
        # check whether an attachment with the same name already exists
        exists = False
        for att in attachments:
            if att.name == name:
                if override:
                    # overwrite it if the user selected to do so
                    attachments.remove(att)
                    att.delete()
                else:
                    exists = True
                break

        if not exists:
            att = Attachment(name=name)
            att.save_file_file(name, content)
            att.save()
            return att


    def update_post_ids(self, att_ids, post_id):
        """
        Update the post_id of a few unbound attachments with only one query.
        :Parameters:

            att_ids
                A list of the attachment's ids.
            post_id
                The new post id.
        """
        if not att_ids:
            return False
        cur = connection.cursor()
        cur.execute('''
            update forum_attachment
            set post_id = %%s
            where id in (%s) and
                   post_id IS NULL
        ''' % ', '.join(('%s',) * len(att_ids)),
            (post_id,) + tuple(att_ids))
        cur.close()
        connection._commit()


class PollManager(models.Manager):

    def create(self, question, options, limit=None, multiple=False,
               topic_id=None):
        now = datetime.utcnow()
        p = Poll(question=question, start_time=now, multiple_votes=multiple,
                 end_time=limit and now + limit or None, topic_id=topic_id)
        p.save()

        for name in options:
            option = PollOption(poll=p, name=name)
            option.save()

        return p

    def update_topic_ids(self, poll_ids, topic_id):
        """
        Update the topic_id of a few unbound polls with only one query.
        :Parameters:

            poll_ids
                A list of the ids of the polls.
            topic_id
                The new topic id.
        """
        if not poll_ids:
            return False
        cur = connection.cursor()
        cur.execute('''
            update forum_poll
            set topic_id = %%s
            where id in (%s) and
                  topic_id IS NULL
        ''' % ', '.join(('%s',) * len(poll_ids)),
            (topic_id,) + tuple(poll_ids))
        cur.close()
        connection._commit()

    def do_vote(self, user_id, options, polls):
        """
        Save the user's vote for one or more vote options in the database.
        :Parameters:

            user_id
                The id of the user who votes
            options
                The list of ids of the poll options the user votes for
            polls
                A list of the polls containing `polls`.  The user will not be
                able to vote in these polls anymore.
        """
        cur = connection.cursor()
        cur.execute('''
            update forum_polloption
             set votes = votes + 1
             where id in (%s)
        ''' % ', '.join(('%s',) * len(options)), options)
        cur.execute('''
            insert into forum_voter (voter_id, poll_id)
                values %s
        ''' % ','.join(('(%s,%%s)' % user_id,) * len(polls)), polls)
        cur.close()
        connection._commit()

    def get_polls(self, topic_id):
        """
        This function returns a list of dicts representing polls that belong
        to the topic `topic_id`.
        The dictionaries have these attributes:
            id
                The poll's id.
            question
                The question of the poll.
            multiple
                Can the user vote for more than one poll option or not?
            options
                A list of dicts representing the poll's choices.
                Their attributes are:
                    id
                        The id of the poll option.
                    name
                        The name of the poll option that is shown to the
                        users.
                    votes
                        The count of users who have voted for this option.

        Normally you should prefer using this function because it is much
        more performant than a sollution using django's orm.
        """
        polls = {}
        cur = connection.cursor()
        cur.execute('''
            select p.id, p.question, p.multiple_votes, o.id, o.name, o.votes
             from forum_poll p, forum_polloption o
             where p.id = o.poll_id and
                   p.topic_id = %s
             order by o.id asc
        ''', [topic_id])
        for row in cur.fetchall():
            poll_id = row[0]
            option = {
                'id':    row[3],
                'name':  row[4],
                'votes': row[5]
            }
            if poll_id in polls:
                polls[poll_id]['options'][option['id']] = option
            else:
                polls[poll_id] = {
                    'id':           row[0],
                    'question':     row[1],
                    'multiple':     row[2],
                    'options':      {
                        option['id']:   option
                    },
                    # this will be queried later
                    'participated': False
                }
        cur.close()

        # get the polls the user has already participated in
        cur = connection.cursor()
        cur.execute('''
            select p.id
             from forum_poll p, forum_voter v
             where p.id = v.poll_id and
                   p.id in (%s)
        ''' % ', '.join(('%s',) * len(polls)), polls.keys())
        for poll in cur.fetchall():
            polls[poll[0]]['participated'] = True
        cur.close()

        return polls

    def calculate_percentage(self, polls):
        """
        This takes a list object generated by `get_polls` as first argument
        and adds the percentage of the votes to the poll option's
        dictionaries.
        """
        # calculate the percentage of the options for all polls
        for poll in polls.values():
            count = sum([o['votes'] for o in poll['options'].values()])
            for option in poll['options'].values():
                if count == 0:
                    option['percent'] = 0
                else:
                    option['percent'] = int(round(option['votes'] / count *
                                                                        100))



class Forum(models.Model):
    """
    This is a forum that may contain subforums or threads.
    If parent is None this forum is a root forum, else it's a subforum.
    Position is an integer that's used to sort the forums.  The lower position
    is, the higher the forum is displayed.
    """
    objects = ForumManager()
    name = models.CharField('Name', max_length=100)
    slug = models.CharField('Slug', max_length=100, blank=True, unique=True)
    description = models.TextField('Beschreibung', max_length=500, blank=True)
    parent = models.ForeignKey('self', null=True, blank=True,
                               verbose_name='Elternforum')
    position = models.IntegerField('Position', default=0)
    last_post = models.ForeignKey('Post', null=True, blank=True)
    post_count = models.IntegerField(blank=True)
    topic_count = models.IntegerField(blank=True, default=0)

    welcome_message = models.ForeignKey('WelcomeMessage', null=True,
                                        blank=True)

    def get_absolute_url(self, action='show'):
        return href(*{
            'show': ('forum', self.parent_id and 'forum' or 'category', self.slug),
            'newtopic': ('forum', 'forum', self.slug, 'newtopic'),
            'welcome': ('forum', 'forum', self.slug, 'welcome'),
            'edit': ('admin', 'forum', 'edit', self.id)
        }[action])

    @property
    def children(self):
        struct = Forum.objects.get_forum_structure()
        return [struct[c]['forum'] for c in struct[self.id]['children']]

    @property
    def topics(self):
        return self.topic_set.all()

    @property
    def parents(self):
        """Return a list of all parent forums up to the root level."""
        struct = Forum.objects.get_forum_structure()
        return [struct[c]['forum'] for c in struct[self.id]['parents']]

    def save(self):
        if not self.slug:
            self.slug = slugify(self.name)
        self.post_count = self.post_count or 0
        self.topic_count = self.topic_count or 0
        super(Forum, self).save()
        cache.delete('forum/structure')

    def get_read_status(self, user):
        """
        Determine the read status of the whole forum for a specific
        user.
        """
        if user.is_anonymous or self.last_post_id <= user.forum_last_read:
            return True
        for forum in self.children:
            if not forum.get_read_status(user):
                return False
        for topic in self.topic_set.all():
            if not topic.get_read_status(user):
                return False
        return True

    def mark_read(self, user):
        """
        Mark all topics in this forum and all related subforums as
        read for the specificed user.
        """
        forums = [self]
        while forums:
            forum = forums.pop()
            for topic in forum.topics:
                topic.mark_read(user)
            forums.extend(forum.children)

    def find_welcome(self, user):
        """
        Return a forum with an unread welcome message if exits.
        The message itself, can be retrieved late, by reading the
        welcome_message attribute.
        """
        forums = self.parents
        forums.append(self)
        read = user.is_authenticated and user.forum_welcome and \
                set(int(i) for i in user.forum_welcome.split(',')) \
                or set()
        for forum in forums:
            if forum.welcome_message_id is not None and \
               forum.id not in read:
                return forum
        return None

    def read_welcome(self, user, read=True):
        if user.is_anonymous:
            return
        status = user.forum_welcome and \
                set(int(i) for i in user.forum_welcome.split(',')) or set()
        if read:
            status.add(self.id)
        else:
            status.discard(self.id)
        user.forum_welcome = ','.join(str(i) for i in status)
        user.save()

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return '<%s id=%s slug=%s name=%s>' % (
            self.__class__.__name__,
            self.id,
            self.slug.encode('utf-8'),
            self.name.encode('utf-8')
        )

    class Meta:
        ordering = ('position', 'name')
        verbose_name = 'forum'
        verbose_name_plural = 'foren'


class Topic(models.Model):
    """
    A topic symbolizes a bunch of Posts (at least one) that is located inside
    a Forum.
    When creating a new topic, a new post is added to it automatically.
    """
    objects = TopicManager()
    forum = models.ForeignKey(Forum, verbose_name='Forum')
    title = models.CharField('Titel', max_length=100)
    slug = models.CharField('Slug', unique=True, max_length=50, null=True)
    view_count = models.IntegerField('Aufrufe', default=0)
    post_count = models.IntegerField('Antworten', default=0)
    #: sticky topics are placed at the top of forum view
    sticky = models.BooleanField(default=False)
    solved = models.BooleanField(u'Gelöst', default=False)
    locked = models.BooleanField('Geschlossen', default=False)
    #: If this TextField is not empty, the moderators see this topic as
    #: "reported".
    reported = models.TextField('Gemeldet', blank=True, null=True)
    #: The user who reported this topic
    reporter = models.ForeignKey(User, blank=True, null=True)
    #: Moderators can set hidden to True which means that the normal users
    #: can't see this topic anymore.
    hidden = models.BooleanField(default=False)
    ubuntu_version = models.CharField(max_length=5, blank=True, null=True)
    ubuntu_distro = models.CharField(max_length=40, blank=True, null=True)
    author = models.ForeignKey(User, related_name='topics')
    first_post = models.ForeignKey('Post', blank=True, null=True,
                                  related_name='topic_first_post_set')
    last_post = models.ForeignKey('Post', blank=True, null=True,
                                  related_name='topic_last_post_set')
    ikhaya_article = models.ForeignKey(Article, blank=True, null=True,
                                       related_name='forum_topic_set')
    has_poll = models.BooleanField(default=False)

    def reply(self, text, author=None, pub_date=None):
        post = Post(text=text, author=author or r.request.user,
                    pub_date=pub_date or datetime.utcnow(), topic=self)
        post.save()
        self.post_count += 1
        self.last_post = post
        self.forum.last_post = post
        self.forum.post_count += 1
        self.forum.save()
        self.save()
        return post

    def touch(self):
        """Increment the view count in a safe way."""
        cur = connection.cursor()
        cur.execute('''
            update forum_topic
               set view_count = view_count + 1
             where id = %s;
        ''', [self.id])
        cur.close()
        connection._commit()

    def get_absolute_url(self, action='show'):
        return href(*{
            'show': ('forum', 'topic', self.slug),
            'reply': ('forum', 'topic', self.slug, 'reply'),
            'report': ('forum', 'topic', self.slug, 'report'),
            'split': ('forum', 'topic', self.slug, 'split'),
            'move': ('forum', 'topic', self.slug, 'move'),
            'lock': ('forum', 'topic', self.slug, 'lock'),
            'unlock': ('forum', 'topic', self.slug, 'unlock'),
            'restore': ('forum', 'topic', self.slug, 'restore'),
            'delete': ('forum', 'topic', self.slug, 'delete'),
            'hide': ('forum', 'topic', self.slug, 'hide'),
            'solve': ('forum', 'topic', self.slug, 'solve'),
            'unsolve': ('forum', 'topic', self.slug, 'unsolve'),
            'subscribe': ('forum', 'topic', self.slug, 'subscribe'),
            'unsubscribe': ('forum', 'topic', self.slug, 'unsubscribe')
        }[action])

    def save(self):
        if self.slug is None:
            slug_words = slugify(self.title).split('-')
            while len('-'.join(slug_words)) > 50:
                slug_words.pop()
            if not slug_words:
                slug_words.append(str(random.randrange(10, 5000)))
                prefix_id = True
            elif slug_words[0].isdigit():
                prefix_id = True
            else:
                try:
                    Topic.objects.get(slug='-'.join(slug_words))
                except Topic.DoesNotExist:
                    prefix_id = False
                else:
                    prefix_id = True
            if not prefix_id:
                self.slug = '-'.join(slug_words)
            else:
                # create a unique id until we can fill the real
                # slug in
                self.slug = '%sX%s' % (
                    random.random(),
                    random.random()
                )[:50]
        else:
            prefix_id = False
        super(Topic, self).save()
        # now that we have the post id we can put it into the slug
        if prefix_id:
            slug_words.insert(0, str(self.id))
            self.slug = '-'.join(slug_words)[:50]
            self.save()

    def delete(self):
        """
        This function removes all posts in this topic first to prevent
        database integrity errors.
        """
        # XXX: Update search
        self.first_post = None
        self.last_post = None
        self.deregister()
        self.save()
        cur = connection.cursor()
        cur.execute('''
            delete from forum_post
              where topic_id = %s
        ''', [self.id])
        cur.close()
        connection._commit()
        super(Topic, self).delete()

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

    def get_pagination(self, threshold=3, ellipsis='...\n', commata=',\n'):
        total = self.post_count - 1
        pages = total // POSTS_PER_PAGE + 1
        if pages == 1:
            return u''
        result = []
        was_ellipsis = False
        for num in xrange(1, pages + 1):
            if num <= threshold or num > pages - threshold:
                if result and result[-1] != ellipsis:
                    result.append(commata)
                was_space = False
                link = self.get_absolute_url()
                if num != 1:
                    link = '%s%d/' % (link, num)
                result.append(u'<a href="%s">%s</a>' % (link, num))
            elif not was_ellipsis:
                was_ellipsis = True
                result.append(ellipsis)
        return u'(%s)' % u''.join(result)

    @property
    def paginated(self):
        return bool(((self.post_count) // (POSTS_PER_PAGE)))

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
        if user.is_anonymous or self.last_post_id <= user.forum_last_read:
            return  user.is_anonymous or self.last_post_id <= user.forum_last_read
        try:
            read_status = cPickle.loads(str(user.forum_read_status))         #get set of read posts from user object
        except:
            read_status = set()
        if self.last_post_id in read_status:
            return True
        else:
            return False

    def mark_read(self, user):
        """
        Mark the current topic as read for a given user.
        """
        try:
            read_status = cPickle.loads(str(user.forum_read_status))
        except:
            read_status = set()
        if self.last_post_id and not self.last_post_id in read_status:
            read_status.add(self.last_post.id)
            maxid = Post.objects.get_max_id()
            if user.forum_last_read < maxid - settings.FORUM_LIMIT_UNREAD:
                user.forum_last_read = maxid - settings.FORUM_LIMIT_UNREAD//2
                read_status = set([x for x in read_status if x >
                                            user.forum_last_read])
            user.forum_read_status = cPickle.dumps(read_status)
            user.save()

    def __unicode__(self):
        return self.title

    def __repr__(self):
        return '<%s id=%s title=%s>' % (
            self.__class__.__name__,
            self.id,
            self.title.encode('utf8')
        )

    class Meta:
        ordering = ['-sticky', '-last_post']


class Post(models.Model):
    """
    Represents a post in a topic.
    """
    objects = PostManager()
    text = models.TextField('Text')
    rendered_text = models.TextField('RenderedText')
    author = models.ForeignKey(User, verbose_name='Autor',
                               related_name='posts')
    pub_date = models.DateTimeField('Datum')
    topic = models.ForeignKey(Topic, verbose_name='Topic')
    #: Moderators can set hidden to True which means that normal users aren't
    #: able to see the post anymore.
    hidden = models.BooleanField(u'Verborgen', default=False)

    def render_text(self, request=None, format='html', nocache=False):
        context = RenderContext(request or r.request, simplified=True)
        if nocache or self.id is None or format != 'html':
            return parse(self.text).render(context, format)
        key = 'forum/post/%s' % self.id
        instructions = cache.get(key)
        if instructions is None:
            instructions = parse(self.text).compile(format)
            cache.set(key, instructions)
        return render(instructions, context)

    def save(self):
        self.rendered_text = self.render_text()
        super(Post, self).save()
        cache.delete('forum/post/%d' % self.id)
        for page in range(1, 5):
            cache.delete('forum/topics/%d/%d' % (self.topic.forum_id, page))
            cache.delete('forum/topics/%dm/%d' % (self.topic.forum_id, page))
        self.update_search()

    def update_search(self):
        """
        This updates the xapian search index.
        """
        search.queue('f', self.id)

    def get_absolute_url(self, action='show'):
        return href(*{
            'show': ('forum', 'post', self.id),
            'edit': ('forum', 'post', self.id, 'edit'),
            'quote': ('forum', 'post', self.id, 'quote'),
            'restore': ('forum', 'post', self.id, 'restore'),
            'delete': ('forum', 'post', self.id, 'delete'),
            'hide': ('forum', 'post', self.id, 'hide')
        }[action])

    def deregister(self):
        """
        This function removes all relations to this post.
        """
        if self.id == self.topic.last_post.id:
            try:
                self.topic.last_post = self.topic.post_set.order_by('id') \
                                .exclude(id=self.id)[0]
            except IndexError:
                self.topic.last_post = None
            self.topic.save()
        if self.id == self.topic.forum.last_post.id:
            cur = connection.cursor()
            cur.execute('''
                select p.id
                 from forum_post p, forum_topic t, forum_forum f
                 where p.topic_id = t.id and
                       t.forum_id = %s and
                       p.id != %s
                 order by id desc
                 limit 1
            ''', [self.topic.forum.id, self.id])
            try:
                self.topic.forum.last_post_id = cur.fetchone()[0]
            except TypeError:
                self.topic.forum.last_post = None
            self.topic.forum.save()

    def delete(self):
        """
        This removes all relations to this post (to prevent database integrity
        errors) and deletes it.
        """
        # XXX: Update search
        self.deregister()
        super(Post, self).delete()

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

    class Meta:
        ordering = ('id',)
        get_latest_by = 'id'


class Attachment(models.Model):
    """
    Posts can have uploaded data associated, this table holds the  mapping
    to the uploaded file on the file system.
    It has these fields:
    `file`
        The path to the attachment itself.
    `name`
        The name of the attachment.
    `post`
        The post the attachment belongs to.  It may be NULL if the attachment
        belongs to a post that is not yet created.
    """
    objects = AttachmentManager()
    file = models.FileField(upload_to='forum/attachments/%S/%W')
    name = models.CharField(max_length=255)
    post = models.ForeignKey(Post, null=True)

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


class Poll(models.Model):
    objects = PollManager()
    question = models.CharField(max_length=100)
    topic = models.ForeignKey(Topic, blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(blank=True, null=True)
    multiple_votes = models.BooleanField(default=False)


class PollOption(models.Model):
    poll = models.ForeignKey(Poll)
    name = models.CharField(max_length=100)
    votes = models.IntegerField(default=0)


class Voter(models.Model):
    voter = models.ForeignKey(User)
    poll = models.ForeignKey(Poll)


class Privilege(models.Model):
    group = models.ForeignKey(Group, null=True)
    user = models.ForeignKey(User, null=True, related_name='forum_privileges')
    forum = models.ForeignKey(Forum)
    can_read = models.BooleanField(default=False)
    can_reply = models.BooleanField(default=False)
    can_create = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_revert = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_sticky = models.BooleanField(default=False)
    can_vote = models.BooleanField(default=False)
    can_create_poll = models.BooleanField(default=False)
    can_upload = models.BooleanField(default=False)
    can_moderate = models.BooleanField(default=False)


class WelcomeMessage(models.Model):
    """
    This class can be used, to attach additional Welcome-Messages to
    a category or forum.  That might be usefull for greeting the users or
    explaining extra rules.  The message will be displayed only once for
    each user.
    """
    title = models.CharField(max_length=120)
    text = models.TextField('Nachricht')
    rendered_text = models.TextField('Gerenderte Nachricht')

    def save(self):
        self.rendered_text = self.render_text()
        super(WelcomeMessage, self).save()

    def render_text(self, request=None, format='html'):
        context = RenderContext(request or r.request, simplified=True)
        return parse(self.text).render(context, format)
