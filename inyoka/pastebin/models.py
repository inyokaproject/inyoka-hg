# -*- coding: utf-8 -*-
"""
    inyoka.pastebin.models
    ~~~~~~~~~~~~~~~~~~~~~~

    Database models for the pastebin.

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
from urlparse import urlparse
from django.db import models
from inyoka.portal.user import User
from inyoka.utils.urls import href, is_safe_domain
from inyoka.utils.decorators import deferred
from inyoka.utils.highlight import highlight_code


class Entry(models.Model):
    title = models.CharField('Titel', max_length=40)
    lang = models.CharField('Sprache', max_length=20)
    code = models.TextField('Code')
    rendered_code = models.TextField('Gerenderter Code')
    pub_date = models.DateTimeField('Datum')
    author = models.ForeignKey(User, verbose_name='Autor')
    referrer = models.TextField('Verweisende Seiten', blank=True)

    class Meta:
        verbose_name = 'Eintrag'
        verbose_name_plural = 'Einträge'
        ordering = ('-id',)

    @deferred
    def referrer_list(self):
        return [x for x in self.referrer.splitlines() if x]

    def add_referrer(self, referrer):
        if is_safe_domain(referrer):
            # take sure that the referrer isn't a pastebin url
            netloc = urlparse(referrer)[1]
            if ('.' + netloc).endswith(('.' + urlparse(href('pastebin'))[1])):
                return False
            if '?' in referrer:
                referrer = referrer.split('?')[0]
            r = self.referrer_list
            if referrer in r:
                return False
            r.append(referrer)
            self.referrer = u'\n'.join(sorted(r))
            deferred.clear(self)
            return True
        return False

    def get_absolute_url(self, action='show'):
        return href(*{
            'show': ('pastebin', self.id),
            'raw': ('pastebin', 'raw', self.id)
        }[action])

    def save(self):
        self.rendered_code = highlight_code(
            self.code,
            self.lang
        )
        super(Entry, self).save()
