# -*- coding: utf-8 -*-
"""
    inyoka.portal.models
    ~~~~~~~~~~~~~~~~~~~~

    Models for the portal.

    :copyright: Copyright 2007-2008 by Armin Ronacher, Christopher Grebs,
                                  Benjamin Wiegand, Christoph Hack,
                                  Marian Sigler.
    :license: GNU GPL.
"""
from django.db import models, connection
from inyoka.utils.text import slugify
from inyoka.utils.urls import href
from inyoka.utils.local import current_request
from inyoka.utils.dates import format_specific_datetime, \
     date_time_to_datetime, natural_date
from inyoka.utils.html import escape
from inyoka.utils.cache import cache
from inyoka.wiki.models import Page
from inyoka.forum.models import Forum, Topic
from inyoka.wiki.parser import parse, render, RenderContext
from inyoka.portal.user import User
from werkzeug import cached_property


class SubscriptionManager(models.Manager):
    """
    Manager class for the `Subscription` model.
    """

    def user_subscribed(self, user, topic=None, forum=None, wiki_page=None):
        if topic is not None:
            column = 'topic_id'
            if isinstance(topic, int):
                ident = topic
            else:
                ident = topic.id
        elif forum is not None:
            column = 'forum_id'
            if isinstance(forum, int):
                ident = forum
            else:
                ident = forum.id
        elif wiki_page is not None:
            column = 'wiki_page_id'
            ident = wiki_page.id
        else:
            raise TypeError('user_subscribed takes exactly 3 arguments (2 given)')
        cursor = connection.cursor()
        cursor.execute('''
            select 1 from portal_subscription
             where user_id = %%s and %s = %%s
        ''' % column, [user.id, ident])
        row = cursor.fetchone()
        cursor.close()
        return row is not None

    def delete_list(self, ids):
        if not ids:
            return
        cur = connection.cursor()

        query = '''
            delete from portal_subscription
             where id in (%(id_list)s)
        ''' % {'id_list': ','.join(['%s'] * len(ids))}

        params = [int(i) for i in ids]

        cur.execute(query, params)
        cur.close()
        connection._commit()


class SessionInfo(models.Model):
    """
    A special class that holds session information.  Not every session
    automatically has a session info.  Basically every user that is
    active has a session info that is updated every request.  The
    management functions for this model are in `inyoka.utils.sessions`.
    """
    key = models.CharField(max_length=200, unique=True)
    last_change = models.DateTimeField()
    subject_text = models.CharField(max_length=100, null=True)
    subject_type = models.CharField(max_length=20)
    subject_link = models.CharField(max_length=200, null=True)
    action = models.CharField(max_length=500)
    action_link = models.CharField(max_length=200, null=True)
    category = models.CharField(max_length=200, null=True)




PRIVMSG_FOLDERS_DATA = (
    (0, 'sent', u'Gesendet'),
    (1, 'inbox', u'Posteingang'),
    (2, 'trash', u'Papierkorb'),
    (3, 'archive', u'Archiv'))

PRIVMSG_FOLDERS = {}
for folder in PRIVMSG_FOLDERS_DATA:
    PRIVMSG_FOLDERS[folder[0]] = PRIVMSG_FOLDERS[folder[1]] = folder


class PrivateMessage(models.Model):
    """
    Private messages allow users to communicate with each other privately.
    This model represent one of these messages.
    """
    #objects = PrivateMessageManager()
    author = models.ForeignKey(User)
    subject = models.CharField(u'Titel', max_length=255)
    pub_date = models.DateTimeField(u'Datum')
    text = models.TextField(u'Text')

    class Meta:
        ordering = ('-pub_date',)

    def send(self, recipients):
        self.save()
        PrivateMessageEntry(message=self, user=self.author, read=True,
                            folder=PRIVMSG_FOLDERS['sent'][0]).save()
        for recipient in recipients:
            cache.delete('portal/pm_count/%s' % recipient.id)
            PrivateMessageEntry(message=self, user=recipient, read=False,
                                folder=PRIVMSG_FOLDERS['inbox'][0]).save()

    @property
    def recipients(self):
        if not hasattr(self, '_recipients'):
            entries = PrivateMessageEntry.objects.filter(message=self) \
                      .exclude(user=self.author)
            self._recipients = [e.user for e in entries]
        return self._recipients

    @property
    def author_avatar(self):
        return self.author.get_profile()

    @property
    def rendered_text(self):
        context = RenderContext(current_request)
        return parse(self.text).render(context, 'html')

    def get_absolute_url(self, action='show'):
        if action == 'show':
            return href('portal', 'privmsg', self.id)
        if action == 'reply':
            return href('portal', 'privmsg', 'new', reply_to=self.id)
        if action == 'forward':
            return href('portal', 'privmsg', 'new', forward=self.id)


class PrivateMessageEntry(models.Model):
    """
    A personal entry for each person who is affected by the private
    message.  This entry can be moved between folders and stores the
    read status flag.
    """
    message = models.ForeignKey('PrivateMessage')
    user = models.ForeignKey(User)
    read = models.BooleanField(u'Gelesen')
    folder = models.SmallIntegerField(u'Ordner', null=True,
                 choices=[(f[0], f[1]) for f in PRIVMSG_FOLDERS_DATA])

    @property
    def folder_name(self):
        return PRIVMSG_FOLDERS[self.folder][2]

    @property
    def is_own_message(self):
        return self.user.id == self.message.author.id

    @property
    def in_archive(self):
        return self.folder == PRIVMSG_FOLDERS['archive'][0]

    def get_absolute_url(self, action='view'):
        if action == 'view':
            return href('portal', 'privmsg', PRIVMSG_FOLDERS[self.folder][1],
                        self.id)
        elif action == 'reply':
            return href('portal', 'privmsg', 'new', reply_to=self.message_id)
        elif action == 'forward':
            return href('portal', 'privmsg', 'new', forward=self.message_id)

    def delete(self):
        if self.folder == PRIVMSG_FOLDERS['trash'][0]:
            self.folder = None
        else:
            self.folder = PRIVMSG_FOLDERS['trash'][0]
            #XXX: if every user deleted it the pn must be deleted completely
        self.save()
        return True

    def archive(self):
        if self.folder != PRIVMSG_FOLDERS['archive'][0]:
            self.folder = PRIVMSG_FOLDERS['archive'][0]
            self.save()
            return True
        return False

    def restore(self):
        if self.folder != PRIVMSG_FOLDERS['trash'][0]:
            return False
        f = self.user == self.message.author and 'sent' or 'inbox'
        self.folder = PRIVMSG_FOLDERS[f][0]
        self.save()
        return True

    class Meta:
        #XXX: Ordering don't work as expected - maybe a django bug?
        order_with_respect_to = 'message'
        #ordering = ('message__pub_date',)


class StaticPage(models.Model):
    """
    Stores static pages (imprint, license, etc.)
    """
    key = models.SlugField(u'Schlüssel', max_length=25, primary_key=True,
          unique=True, help_text=u'Wird für die URL verwendet.'\
                                 u' Kann nicht verändert werden.')
    title = models.CharField(u'Titel', max_length=200)
    content = models.TextField(u'Inhalt',
        help_text=(u'Muss valides XHTML sein. Überschriften ab h3 abwärts.')
    )

    class Meta:
        verbose_name = 'statische Seite'
        verbose_name_plural = 'statische Seiten'


    def __repr__(self):
        return '<%s:%s "%s">' % (
                self.__class__.__name__,
                self.key,
                self.title,
            )

    def __unicode__(self):
        return self.title

    def get_absolute_url(self, action='show'):
        return href(*{
            'show': ('portal', self.key),
            'edit': ('admin', 'pages', 'edit', self.key),
            'delete': ('admin', 'pages', 'delete', self.key)
        }[action])


class StaticFile(models.Model):
    identifier = models.CharField('Identifier', max_length=100, unique=True)
    file = models.FileField(upload_to='portal/files')
    is_ikhaya_icon = models.BooleanField('Ist Ikhaya-Icon', default=False)

    def __unicode__(self):
        return self.identifier

    def get_absolute_url(self, action='show'):
        if action == 'show':
            return self.file.path
        return href(*{
            'edit': ('admin', 'files', 'edit', self.identifier),
            'delete': ('admin', 'files', 'delete', self.identifier)
        }[action])


class Subscription(models.Model):
    objects = SubscriptionManager()
    user = models.ForeignKey(User)
    #topic = models.ForeignKey(Topic, null=True)
    #forum = models.ForeignKey(Forum, null=True)
    topic_id = models.IntegerField(null=True)
    forum_id = models.IntegerField(null=True)
    wiki_page = models.ForeignKey(Page, null=True)
    notified = models.BooleanField('User was already notified',
                                   default=False)

    @cached_property
    def topic(self):
        if self.topic_id:
            return Topic.query.get(self.topic_id)

    @cached_property
    def forum(self):
        if self.forum_id:
            return Forum.query.get(self.forum_id)

    def __unicode__(self):
        if self.topic:
            type = u'topic'
            title = self.topic.title
        elif self.wiki_page:
            type = u'wiki_page'
            title = self.wiki_page.name
        elif self.forum:
            type = u'forum'
            title = self.forum.name
        return u'Subscription(%s, %s:"%s")' % (
            self.user.username,
            type, title
        )

    class Meta:
        unique_together = (
            ('topic_id', 'user'),
            ('forum_id', 'user'),
            ('wiki_page', 'user'),
        )


class Event(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True) # this may change !!
    changed = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)
    date = models.DateField()
    time = models.TimeField(blank=True, null=True) # None -> whole day
    description = models.TextField(blank=True)
    author = models.ForeignKey(User)
    location = models.CharField(max_length=25, blank=True)
    location_town = models.CharField(max_length=20, blank=True)
    location_lat = models.FloatField(u'Koordinaten (Länge)',
                                     blank=True, null=True)
    location_long = models.FloatField('Koordinaten (Breite)',
                                      blank=True, null=True)

    def get_absolute_url(self, action='show'):
        return href(*{
            'show': ('portal', 'calendar', self.slug),
            'edit': ('admin', 'events', 'edit', self.id),
            'delete': ('admin', 'events', 'delete', self.id),
            'new': ('admin', 'events', 'new'),
        }[action])

    @property
    def rendered_description(self):
        context = RenderContext(current_request)
        key = 'ikhaya/date/%s' % self.id
        instructions = cache.get(key)
        if instructions is None:
            instructions = parse(self.description).compile('html')
            cache.set(key, instructions)
        return render(instructions, context)

    def save(self):
        i = 0
        while True:
            slug = self.date.strftime('%Y/%m/%d/') + slugify(self.name) + \
                   (i and '-%d' % i or '')
            try:
                event = Event.objects.get(slug=slug)
            except Event.DoesNotExist:
                break
            else:
                if event.id == self.id:
                    break
                i += 1
        self.slug = slug
        super(self.__class__, self).save()
        cache.delete('ikhaya/event/%s' % self.id)

    def __repr__(self):
        return u'<Event %r (%s)>' % (
            self.name,
            self.date.strftime('%Y-%m-%d')
        )

    def friendly_title(self, with_date=True, with_html_link=False):
        if with_date:
            if self.time == None:
                s_date = ' ' + natural_date(self.date, prefix=True)
            else:
                s_date = ' ' + format_specific_datetime(date_time_to_datetime(
                                   self.date, self.time), alt=True)
        else:
            s_date = ''
        s_location = self.location_town \
            and u' in %s' % self.location_town \
            or ''
        if with_html_link:
            return u'<a href="%s" class="event_link">%s</a>%s%s' % (
                escape(self.get_absolute_url(), True),
                escape(self.name),
                escape(s_date),
                escape(s_location),
            )
        else:
            return self.name + s_date + s_location

    @property
    def natural_datetime(self):
        if self.time == None:
            return ' ' + natural_date(self.date, prefix=True)
        else:
            return ' ' + format_specific_datetime(date_time_to_datetime(
                         self.date, self.time), alt=True)

    @property
    def natural_coordinates(self):
        if self.location_lat and self.location_long:
            lat = self.location_lat > 0 and u'%g° N' % self.location_lat \
                                        or u'%g° S' % -self.location_lat
            long = self.location_long > 0 and u'%g° O' % self.location_long\
                                          or u'%g° W' % -self.location_long
            return u'%s, %s' % (lat, long)
        else:
            return u''

    @property
    def coordinates_url(self):
        lat = self.location_lat > 0 and '%g_N' % self.location_lat \
                                    or '%g_S' % -self.location_lat
        long = self.location_long > 0 and '%g_E' % self.location_long\
                                      or '%g_W' % -self.location_long
        return 'http://tools.wikimedia.de/~magnus/geo/geohack.php?language' \
               '=de&params=%s_%s' % (lat, long)


class SearchQueueManager(models.Manager):
    def append(self, component, doc_id):
        """Append an item to the queue for later indexing."""
        item = self.model()
        item.component = component
        item.doc_id = doc_id
        item.save()

    def select_blocks(self, block_size=100):
        """
        Fetch all elements in blocks from the search queue.
        Note that the elements automatically get deleted.
        """
        fetch = lambda: self.all()[:block_size]
        items = fetch()
        while items:
            last_id = 0
            for item in items:
                last_id = item.id
                yield (item.component, item.doc_id)
            SearchQueue.objects.remove(last_id)
            items = fetch()

    def remove(self, last_id):
        """
        Remove all elements, which are smaller (or equal)
        than last_id from the queue."""
        cursor = connection.cursor()
        cursor.execute('''
            delete from portal_searchqueue
                  where id <= %d
        ''' % last_id)
        cursor.close()
        connection._commit()


class SearchQueue(models.Model):
    """
    Managing a to-do list for asynchronous indexing.
    """
    objects = SearchQueueManager()
    component = models.CharField(max_length=1)
    doc_id = models.IntegerField()

    class Meta:
        ordering = ['id']
