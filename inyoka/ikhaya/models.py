# -*- coding: utf-8 -*-
"""
    inyoka.ikhaya.models
    ~~~~~~~~~~~~~~~~~~~~

    Database models for ikhaya.

    :copyright: 2007 by Benjamin Wiegand, Christoph Hack
    :license: GNU GPL, see LICENSE for more details.
"""
import random
from datetime import datetime
from django.db import models, connection
from django.core.cache import cache
from inyoka.portal.user import User
from inyoka.wiki.parser import render, parse, RenderContext
from inyoka.utils import slugify, striptags
from inyoka.utils.urls import href, url_for
from inyoka.utils.search import search
from inyoka.middlewares.registry import r


class ArticleManager(models.Manager):

    def __init__(self, public=True, all=False):
        models.Manager.__init__(self)
        self._public = public
        self._all = all

    def get_query_set(self):
        q = super(ArticleManager, self).get_query_set()
        if not self._all:
            q = q.filter(public=self._public)
            if self._public:
                q = q.filter(pub_date__lt=datetime.now())
            else:
                q = q.filter(pub_date__qt=datetime.now())
        return q


class SuggestionManager(models.Manager):
    def delete(self, ids):
        """
        Deletes a list of suggestions with only one query.
        """
        cur = connection.cursor()
        cur.execute('''
            delete from ikhaya_suggestion
             where id in (%s)
        ''' % ', '.join(['%s'] * len(ids)), list(ids))
        cur.close()
        connection._commit()
        cache.delete('ikhaya/suggestion_count')


class Icon(models.Model):
    identifier = models.CharField('Identifier', max_length=100, unique=True)
    img = models.ImageField(upload_to='ikhaya/icons')

    def __unicode__(self):
        return self.identifier

    def get_absolute_url(self, action='show'):
        if action == 'show':
            return self.get_img_url()
        return href(*{
            'edit': ('admin', 'ikhaya', 'icons', 'edit', self.identifier),
            'delete': ('admin', 'ikhaya', 'icons', 'delete', self.identifier)
        }[action])


class Category(models.Model):
    name = models.CharField(max_length=180)
    slug = models.CharField('Slug', max_length=100, blank=True, unique=True)
    icon = models.ForeignKey(Icon, blank=True, null=True, verbose_name='Icon')

    def __unicode__(self):
        return self.name

    def get_absolute_url(self, action='show'):
        return href(*{
            'show': ('ikhaya', 'category', self.slug),
            'edit': ('admin', 'ikhaya', 'categories', 'edit', self.slug)
        }[action])

    def save(self):
        self.slug = slugify(self.name)
        super(Category, self).save()

    class Meta:
        verbose_name = 'Kategorie'
        verbose_name_plural = 'Kategorien'


class Article(models.Model):
    published = ArticleManager(public=True)
    drafts = ArticleManager(public=False)
    objects = ArticleManager(all=True)

    pub_date = models.DateTimeField('Datum')
    updated = models.DateTimeField('Letzte Änderung', blank=True, null=True)
    author = models.ForeignKey(User, related_name='article_set',
                               verbose_name='Autor')
    subject = models.CharField('Überschrift', max_length=180)
    category = models.ForeignKey(Category, verbose_name='Kategorie')
    icon = models.ForeignKey(Icon, blank=True, null=True, verbose_name='Icon')
    intro = models.TextField('Einleitung')
    text = models.TextField('Text')
    public = models.BooleanField('Veröffentlicht')
    slug = models.CharField('Slug', max_length=100, blank=True, unique=True)
    is_xhtml = models.BooleanField('XHTML Markup', default=False)

    @property
    def rendered_text(self):
        return self._render(self.text)

    @property
    def rendered_intro(self):
        return self._render(self.intro)

    @property
    def simplified_text(self):
        return self._simplify(self.text)

    @property
    def hidden(self):
        """
        This returns a boolean whether this article is not visible for normal
        users.
        Article that are not published or whose pub_date is in the future
        aren't shown for a normal user.
        """
        return not self.public or self.pub_date > datetime.now()

    @property
    def simplified_intro(self):
        return self._simplify(self.intro)

    def get_absolute_url(self, action='show'):
        return href(*{
            'show': ('ikhaya', self.slug),
            'edit': ('admin', 'ikhaya', 'articles', 'edit', self.slug),
            'delete': ('admin', 'ikhaya', 'articles', 'delete', self.slug)
        }[action])

    def __unicode__(self):
        return u'%s - %s' % (
            self.pub_date.strftime('%d.%m.%Y'),
            self.subject
        )

    def _simplify(self, text):
        """Remove markup of a text that belongs to this Article"""
        if self.is_xhtml:
            return striptags(text)
        return parse(text).text

    def _render(self, text):
        """Render a text that belongs to this Article to HTML"""
        print self.is_xhtml
        if self.is_xhtml:
            return text
        node = parse(text)
        return node.render(r.request, 'html')

    def update_search(self):
        """
        This updates the xapian search index.
        """
        search.store(
            component='i',
            uid = self.id,
            title = self.subject,
            author = self.author_id,
            date = self.pub_date,
            category = self.category.slug,
            text = self.text
        )

    def save(self):
        """
        This increases the edit count by 1, generates a new slug and updates
        the xapian database
        """
        suffix_id = False
        if not self.updated or self.updated < self.pub_date:
            self.updated = self.pub_date
        else:
            self.updated = datetime.now()
        if not self.slug:
            if not self.icon:
                # use the category's icon if available
                self.icon = self.category.icon

            # new article
            slug_words = slugify(self.subject).split('-')
            slug = '%s/%s' % (
                self.pub_date.strftime('%Y/%m/%d'),
                '-'.join(slug_words)
            )

            if slug_words[-1].isdigit():
                suffix_id = True
            else:
                try:
                    Article.objects.get(slug=slug)
                except Article.DoesNotExist:
                    suffix_id = False
                else:
                    suffix_id = True
            if not suffix_id:
                self.slug = slug
            else:
                # create a unique id until we can fill the real slug in
                self.slug = '%sX%s' % (
                    random.random(),
                    random.random()
                )[:50]

        super(Article, self).save()
        self.update_search()

        # now that we have the article id we can put it into the slug
        if suffix_id:
            self.slug = '%s-%s' % (slug, self.id)
            super(Article, self).save()

    def delete(self):
        """
        Deletes the xapian document
        """
        Document(self.xapian_docid).delete()
        super(Article, self).delete()

    class Meta:
        verbose_name = 'Artikel'
        verbose_name_plural = 'Artikel'
        ordering = ['-pub_date', 'author']


class Suggestion(models.Model):
    objects = SuggestionManager()
    author = models.ForeignKey(User)
    pub_date = models.DateTimeField('Datum')
    title = models.CharField(max_length=100)
    text = models.TextField()
    intro = models.TextField()

    @property
    def rendered_text(self):
        # XXX: Cache
        context = RenderContext(r.request)
        return parse(self.text).render(context, 'html')

    @property
    def rendered_intro(self):
        # XXX: Cache
        context = RenderContext(r.request)
        return parse(self.intro).render(context, 'html')


class Comment(models.Model):
    article = models.ForeignKey(Article)
    title = models.CharField(max_length=100)
    text = models.TextField()
    author = models.ForeignKey(User)
    pub_date = models.DateTimeField()

    def get_absolute_url(self, action='show'):
        return href('ikhaya', self.article.slug,
                    _anchor='comment_%s' % self.id)

    @property
    def rendered_text(self):
        context = RenderContext(r.request)
        key = 'ikhaya/comment/%s' % self.id
        instructions = cache.get(key)
        if instructions is None:
            instructions = parse(self.text).compile('html')
            cache.set(key, instructions)
        return render(instructions, context)

def recv_article(article_id):
    article = Article.objects.select_related(1).get(id=article_id)
    return {
        'title': article.subject,
        'user': article.author,
        'date': article.pub_date,
        'url': url_for(article),
        'component': u'Ikhaya'
    }
search.register_result_handler('i', recv_article)
