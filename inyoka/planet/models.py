# -*- coding: utf-8 -*-
"""
    inyoka.planet.models
    ~~~~~~~~~~~~~~~~~~~~

    Database models for the planet.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from PIL import Image
from django.db import models
from inyoka.utils.urls import href, url_for
from inyoka.utils.search import search, SearchAdapter
from inyoka.utils.html import striptags
from inyoka.portal.user import User


class Blog(models.Model):
    name = models.CharField(max_length=40)
    description = models.TextField(blank=True, null=True)
    blog_url = models.URLField()
    feed_url = models.URLField()
    icon = models.ImageField(upload_to='planet/icons', blank=True)
    last_sync = models.DateTimeField(blank=True, null=True)
    active = models.BooleanField(default=True)

    @property
    def icon_url(self):
        if not self.icon:
            return href('static', 'img', 'planet', 'anonymous.png')
        return self.icon.url

    def delete(self):
        for entry in self.entry_set.all():
            entry.delete()
        self.icon.delete(save=False)
        super(Blog, self).delete()

    def save_icon(self, img, save=True):
        """Save the icon to the file system."""
        if self.icon:
            self.icon.delete(save=False)
        icon = Image.open(img)
        ext = icon.format.lower()
        if not self.id:
            self.save()
        fn = 'planet/icons/icon_%d.%s' % (self.id, ext)
        self.icon.save(fn, img, save=save)

    def __unicode__(self):
        return self.name

    def get_absolute_url(self, action='show'):
        if action == 'show':
            return self.blog_url
        else:
            return href(*{
                'edit': ('admin', 'planet', 'edit', self.id),
                'delete': ('admin', 'planet', 'delete', self.id)
            }[action])

    class Meta:
        ordering = ('name',)
        verbose_name = 'Blog'
        verbose_name_plural = 'Blogs'


class Entry(models.Model):
    blog = models.ForeignKey(Blog)
    guid = models.CharField(max_length=200, unique=True, db_index=True)
    title = models.CharField(max_length=140)
    url = models.URLField()
    text = models.TextField()
    pub_date = models.DateTimeField()
    updated = models.DateTimeField()
    author = models.CharField(max_length=50)
    author_homepage = models.URLField(blank=True, null=True)
    hidden = models.BooleanField()
    hidden_by = models.ForeignKey(User, blank=True, null=True,
                                  related_name='hidden_planet_posts')

    def __unicode__(self):
        return u'%s / %s' % (
            self.blog,
            self.title
        )

    @property
    def simplified_text(self):
        return striptags(self.text)

    def get_absolute_url(self, action='show'):
        if action == 'show':
            return self.url
        else:
            return href(*{
                'hide':     ('planet', 'hide', self.id),
            }[action])

    def update_search(self):
        """
        This updates the xapian search index.
        """
        PlanetSearchAdapter.queue(self.id)

    def save(self, force_insert=False, force_update=False):
        super(Entry, self).save(force_insert, force_update)
        blog = self.blog
        if (not blog.last_sync or self.updated > blog.last_sync) and blog.active:
            self.update_search()

    def delete(self):
        super(Entry, self).delete()
        # update search
        self.update_search()

    class Meta:
        verbose_name = 'Eintrag'
        verbose_name_plural = u'Einträge'
        get_latest_by = 'pub_date'
        ordering = ('-pub_date',)


class PlanetSearchAdapter(SearchAdapter):
    type_id = 'p'

    def extract_data(self, entry):
        return {'title': entry.title,
                'user': entry.blog.name,
                'user_url': entry.blog.blog_url,
                'date': entry.pub_date,
                'url': url_for(entry),
                'component': u'Planet',
                'group': entry.blog.name,
                'group_url': url_for(entry.blog),
                'text': entry.text,
                'hidden': entry.hidden}

    def recv(self, entry_id):
        entry = Entry.objects.select_related(depth=1).get(id=entry_id)
        return self.extract_data(entry)

    def recv_multi(self, entry_ids):
        entries = Entry.objects.select_related(depth=1).filter(id__in=entry_ids)
        return [self.extract_data(entry) for entry in entries]

    def store(self, entry_id):
        entry = Entry.objects.select_related(depth=1).get(id=entry_id)
        search.store(
            component='p',
            uid=entry.id,
            title=entry.title,
            text=entry.simplified_text,
            date=entry.pub_date,
            category=entry.blog.name
        )

    def get_doc_ids(self):
        ids = Entry.objects.values_list('id', flat=True)
        for id in ids:
            yield id


search.register(PlanetSearchAdapter())
