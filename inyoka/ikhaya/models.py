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
from inyoka.portal.user import User
from inyoka.portal.models import StaticFile
from inyoka.wiki.parser import render, parse, RenderContext
from inyoka.utils.text import slugify
from inyoka.utils.html import striptags
from inyoka.utils.urls import href, url_for
from inyoka.utils.cache import cache
from inyoka.utils.dates import date_time_to_datetime
from inyoka.utils.search import search, SearchAdapter
from inyoka.utils.local import current_request


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
                q = q.filter(pub_date__lte=datetime.utcnow().date())
            else:
                q = q.filter(pub_date__gte=datetime.utcnow().date())
        return q

    def delete(self):
        #XXX: it's not possible to delete an ikhaya article
        #     we first need to delete referenced comments...
        super(ArticleManager, self).delete()


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


class Category(models.Model):
    name = models.CharField(max_length=180)
    slug = models.CharField('Slug', max_length=100, blank=True, unique=True)
    icon = models.ForeignKey(StaticFile, blank=True, null=True,
                             verbose_name='Icon')

    def __unicode__(self):
        return self.name

    def get_absolute_url(self, action='show'):
        return href(*{
            'show': ('ikhaya', 'category', self.slug),
            'edit': ('admin', 'ikhaya', 'categories', 'edit', self.slug)
        }[action])

    def save(self, force_insert=False, force_update=False):
        self.slug = slugify(self.name)
        super(Category, self).save(force_insert, force_update)
        cache.delete('ikhaya/categories')

    class Meta:
        verbose_name = 'Kategorie'
        verbose_name_plural = 'Kategorien'


class Article(models.Model):
    objects = models.Manager()
    published = ArticleManager(public=True)
    drafts = ArticleManager(public=False)

    pub_date = models.DateField('Datum')
    pub_time = models.TimeField('Zeit')
    updated = models.DateTimeField('Letzte Änderung', blank=True, null=True)
    author = models.ForeignKey(User, related_name='article_set',
                               verbose_name='Autor')
    subject = models.CharField('Überschrift', max_length=180)
    category = models.ForeignKey(Category, verbose_name='Kategorie')
    icon = models.ForeignKey(StaticFile, blank=True, null=True,
                             verbose_name='Icon')
    intro = models.TextField('Einleitung')
    text = models.TextField('Text')
    public = models.BooleanField('Veröffentlicht')
    slug = models.CharField('Slug', max_length=100, blank=True)
    is_xhtml = models.BooleanField('XHTML Markup', default=False)
    comment_count = models.IntegerField(default=0)
    comments_enabled = models.BooleanField('Kommentare erlaubt', default=True)

    @property
    def pub_datetime(self):
        return date_time_to_datetime(self.pub_date, self.pub_time)

    def _simplify(self, text, key):
        """Remove markup of a text that belongs to this Article"""
        v = cache.get(key)
        if v:
            return v
        if self.is_xhtml:
            simple = striptags(text)
        else:
            simple = parse(text).text
        cache.set(key, simple)
        return simple

    def _render(self, text, key):
        """Render a text that belongs to this Article to HTML"""
        if self.is_xhtml:
            return text
        context = RenderContext(current_request)
        instructions = cache.get(key)
        if instructions is None:
            instructions = parse(text).compile('html')
            cache.set(key, instructions)
        return render(instructions, context)

    @property
    def rendered_text(self):
        return self._render(self.text, 'ikhaya/article_text/%s' % self.id)

    @property
    def rendered_intro(self):
        return self._render(self.intro, 'ikhaya/article_intro/%s' % self.id)

    @property
    def simplified_text(self):
        return self._simplify(self.text, 'ikhaya/simple_text/%s' % self.id)

    @property
    def simplified_intro(self):
        return self._simplify(self.intro, 'ikhaya/simple_intro/%s' % self.id)

    @property
    def hidden(self):
        """
        This returns a boolean whether this article is not visible for normal
        users.
        Article that are not published or whose pub_date is in the future
        aren't shown for a normal user.
        """
        return not self.public or self.pub_datetime > datetime.utcnow()

    @property
    def comments(self):
        """This returns all the comments for this article"""
        return Comment.objects.filter(article=self)

    def get_absolute_url(self, action='show'):
        stamp = self.pub_date.strftime('%Y/%m/%d')
        return href(*{
            'show': ('ikhaya', stamp, self.slug),
            'edit': ('admin', 'ikhaya', 'articles', 'edit', self.id),
            'delete': ('admin', 'ikhaya', 'articles', 'delete', self.id)
        }[action])

    def __unicode__(self):
        return u'%s - %s' % (
            self.pub_date.strftime('%d.%m.%Y'),
            self.subject
        )

    def update_search(self):
        """
        This updates the xapian search index.
        """
        IkhayaSearchAdapter.queue(self.id)

    def save(self, force_insert=False, force_update=False):
        """
        This increases the edit count by 1 annd updates the xapian database.
        """
        suffix_id = False
        if not self.updated or self.updated < self.pub_datetime:
            self.updated = self.pub_datetime
        else:
            self.updated = datetime.utcnow()
        if not self.slug:
            if not self.icon:
                # use the category's icon if available
                self.icon = self.category.icon

            # new article
            slug = slugify(self.subject)

            if slug.split('-')[-1].isdigit():
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

        super(Article, self).save(force_insert, force_update)
        self.update_search()

        # now that we have the article id we can put it into the slug
        if suffix_id:
            self.slug = '%s-%s' % (slug, self.id)
            cur = connection.cursor()
            cur.execute('''
                update ikhaya_article a set a.slug = %s where a.id = %s
            ''', [self.slug, self.id])
        cache.delete('ikhaya/archive')
        cache.delete('ikhaya/short_archive')

    def delete(self):
        """
        Deletes the xapian document
        """
        id = self.id
        super(Article, self).delete()
        self.id = id
        # update search
        self.update_search()

    class Meta:
        verbose_name = 'Artikel'
        verbose_name_plural = 'Artikel'
        ordering = ['-pub_date', '-pub_time', 'author']
        unique_together = ('pub_date', 'slug')


class Suggestion(models.Model):
    objects = SuggestionManager()
    author = models.ForeignKey(User, related_name='suggestion_set')
    pub_date = models.DateTimeField('Datum')
    title = models.CharField(max_length=100)
    text = models.TextField()
    intro = models.TextField()
    owner = models.ForeignKey(User, related_name='owned_suggestion_set',
                              null=True, blank=True)

    @property
    def rendered_text(self):
        context = RenderContext(current_request)
        key = 'ikhaya/suggestion_text/%s' % self.id
        instructions = cache.get(key)
        if instructions is None:
            instructions = parse(self.text).compile('html')
            cache.set(key, instructions)
        return render(instructions, context)

    @property
    def rendered_intro(self):
        context = RenderContext(current_request)
        key = 'ikhaya/suggestion_intro/%s' % self.id
        instructions = cache.get(key)
        if instructions is None:
            instructions = parse(self.intro).compile('html')
            cache.set(key, instructions)
        return render(instructions, context)


class Comment(models.Model):
    article = models.ForeignKey(Article, null=True)
    text = models.TextField()
    author = models.ForeignKey(User)
    pub_date = models.DateTimeField()
    deleted = models.BooleanField(null=False, default=False)

    def get_absolute_url(self, action='show'):
        return href('ikhaya', self.article.slug,
                    _anchor='comment_%s' % self.id)
    @property
    def rendered_text(self):
        if self.deleted:
            return u'<p class="deleted">Dieses Kommentar wurde von der ' \
                    u'Moderation gelöscht</p>'
        context = RenderContext(current_request)
        key = 'ikhaya/comment/%s' % self.id
        instructions = cache.get(key)
        if instructions is None:
            instructions = parse(self.text).compile('html')
            cache.set(key, instructions)
        return render(instructions, context)

    def save(self, force_insert=False, force_update=False):
        super(Comment, self).save(force_insert, force_update)
        if self.id:
            cache.delete('ikhaya/comment/%d' % self.id)
        self.article.comment_count += 1
        self.article.save()


class ArticleSearchAuthDecider(object):
    """Decides whetever a user can display a search result or not."""

    def __init__(self, user):
        self.now = datetime.utcnow()
        self.priv = user.can('article_edit')

    def __call__(self, auth):
        return self.priv or ((not auth[0]) and auth[1] <= self.now)


class IkhayaSearchAdapter(SearchAdapter):
    type_id = 'i'
    auth_decider = ArticleSearchAuthDecider

    def store(self, docid):
        article = Article.objects.select_related(depth=1).get(id=docid)
        search.store(
            component='i',
            uid=article.id,
            title=article.subject,
            user=article.author_id,
            date=article.pub_date,
            auth=(article.hidden, article.pub_date),
            category=article.category.slug,
            text=[article.text, article.intro]
        )

    def recv(self, docid):
        article = Article.objects.select_related(depth=1).get(id=docid)
        return {
            'title': article.subject,
            'user': article.author,
            'date': article.pub_date,
            'url': url_for(article),
            'component': u'Ikhaya',
            'group': article.category.name,
            'group_url': url_for(article.category),
            'highlight': True,
            'text': u'%s %s' % (article.simplified_intro,
                                article.simplified_text)
        }

    def get_doc_ids(self):
        cur = connection.cursor()
        cur.execute('select id from ikhaya_article')
        for row in cur.fetchall():
            yield row[0]
        cur.close()


search.register(IkhayaSearchAdapter())
