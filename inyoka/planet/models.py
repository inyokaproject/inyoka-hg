# -*- coding: utf-8 -*-
"""
    inyoka.planet.models
    ~~~~~~~~~~~~~~~~~~~~

    Database models for the planet.

    :copyright: 2007 by Benjamin Wiegand, maix.
    :license: GNU GPL, see LICENSE for more details.
"""
import os
from os import path
from PIL import Image
from StringIO import StringIO
from django.conf import settings
from django.db import models
from inyoka.utils import striptags
from inyoka.utils.urls import href
from inyoka.utils.search import search, Document


class Blog(models.Model):
    name = models.CharField(max_length=40)
    description = models.TextField(blank=True, null=True)
    blog_url = models.URLField()
    feed_url = models.URLField()
    icon = models.ImageField(upload_to='planet/icons', blank=True)
    last_sync = models.DateTimeField(blank=True, null=True)

    @property
    def icon_url(self):
        if not self.icon:
            return href('static', 'img', 'planet', 'anonymous.png')
        return self.get_icon_url()

    def delete(self):
        for entry in self.entry_set.all():
            entry.delete()
        self.delete_icon()
        super(Blog, self).delete()

    def delete_icon(self):
        """Delete the icon from the file system."""
        fn = self.get_icon_filename()
        if path.exists(fn):
            os.remove(fn)
        self.icon = None

    def save_icon(self, img):
        """Save the icon to the file system."""
        icon = Image.open(StringIO(img.content))
        actual_path = self.get_icon_filename()
        ext = path.splitext(img.filename)[1][1:]
        fn = 'planet/icons/icon_%d.%s' % (self.id, ext)
        if not actual_path:
            pth = path.join(settings.MEDIA_ROOT, fn)
        else:
            pth = actual_path
        ext = path.splitext(img.filename)[1]
        icon.save(pth, "PNG")
        self.icon = fn

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
    guid = models.CharField(max_length=200, unique=True)
    title = models.CharField(max_length=140)
    url = models.URLField()
    text = models.TextField()
    pub_date = models.DateTimeField()
    updated = models.DateTimeField()
    author = models.CharField(max_length=50)
    author_homepage = models.URLField(blank=True, null=True)
    xapian_docid = models.IntegerField(default=0, blank=True)

    def __unicode__(self):
        return u'%s / %s' % (
            self.blog,
            self.title
        )

    def get_absolute_url(self):
        return self.url

    @property
    def simplified_text(self):
        return striptags(self.text)

    def update_search(self):
        """
        This updates the xapian search index.
        """
        doc = search.create_document('planet', self.xapian_docid)
        doc.clear()
        doc['title'] = self.title
        doc['text'] = self.simplified_text
        doc['date'] = self.updated
        doc['area'] = 'Planet'
        doc.save()
        if self.xapian_docid != doc.docid:
            self.xapian_docid = doc.docid
            models.Model.save(self)

    def save(self):
        self.update_search()
        super(Entry, self).save()

    def delete(self):
        """
        Deletes the xapian document
        """
        Document(self.xapian_docid).delete()
        super(Entry, self).delete()

    class Meta:
        verbose_name = 'Eintrag'
        verbose_name_plural = u'Einträge'
        get_latest_by = 'pub_date'
        ordering = ('-pub_date',)
