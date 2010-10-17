# -*- coding: utf-8 -*-
"""
    inyoka.ikhaya.models
    ~~~~~~~~~~~~~~~~~~~~

    Database models for ikhaya.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from hashlib import md5
from datetime import datetime
from django.db import models, connection
from django.db.models import Q
from inyoka.portal.user import User
from inyoka.portal.models import StaticFile
from inyoka.wiki.parser import render, parse, RenderContext
from inyoka.utils.text import slugify
from inyoka.utils.html import striptags
from inyoka.utils.urls import href, url_for
from inyoka.utils.cache import cache
from inyoka.utils.dates import date_time_to_datetime, datetime_to_timezone
from inyoka.utils.search import search, SearchAdapter
from inyoka.utils.local import current_request
from inyoka.utils.decorators import deferred
from inyoka.utils.database import find_next_django_increment


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
                q = q.filter(Q(pub_date__lt=datetime.utcnow().date())|
                             Q(pub_date = datetime.utcnow().date(), pub_time__lte = datetime.utcnow().time()))
            else:
                q = q.filter(Q(pub_date__gt=datetime.utcnow().date())|
                             Q(pub_date = datetime.utcnow().date(), pub_time__gte = datetime.utcnow().time()))
        return q

    def delete(self):
        #XXX: it's not possible to delete an ikhaya article
        #     we first need to delete referenced comments...
        super(ArticleManager, self).delete()

    def get_cached(self, keys):
        """Get some articles from the cache. `keys` must be a list with
        (pub_date, slug) pairs. Missing entries from the cache are
        automatically fetched from the database. This method should be
        also used for retrieving single objects.

        ATTENTION: All articles which are returned from this function
        don't contain any text or intro (but they will contain rendered_text
        and rendered_intro). So do NEVER save any article returned by
        this function.
        """
        keys = map(lambda x: ('ikhaya/article/%s/%s' % x, x[0], x[1]), keys)
        articles = cache.get_many(*[k[0] for k in keys])
        for i, (key, pub_date, slug) in enumerate(keys):
            if articles[i] is None:
                try:
                    articles[i] = article = self.select_related('author__username',
                        'category').get(slug=slug, pub_date=pub_date)
                except self.model.DoesNotExist:
                    articles[i] = None
                    continue
                # render text and intro (and replace the getter to make caching
                # possible)
                article._rendered_text = unicode(article.rendered_text)
                article._rendered_intro = unicode(article.rendered_intro)
                article.text = None
                article.intro = None
                cache.set(key, article)
        return filter(None, articles)


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
    slug = models.CharField('Slug', max_length=100, blank=True, unique=True, db_index=True)
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
        self.slug = find_next_django_increment(Category, 'slug', slugify(self.name))
        super(Category, self).save(force_insert, force_update)
        cache.delete('ikhaya/categories')

    class Meta:
        verbose_name = 'Kategorie'
        verbose_name_plural = 'Kategorien'


class Article(models.Model):
    objects = ArticleManager(all=True)
    published = ArticleManager(public=True)
    drafts = ArticleManager(public=False)

    pub_date = models.DateField('Datum', db_index=True)
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
    slug = models.SlugField('Slug', max_length=100, blank=True, db_index=True)
    is_xhtml = models.BooleanField('XHTML Markup', default=False)
    comment_count = models.IntegerField(default=0)
    comments_enabled = models.BooleanField('Kommentare erlaubt', default=True)

    @deferred
    def pub_datetime(self):
        return date_time_to_datetime(self.pub_date, self.pub_time)

    @property
    def local_pub_datetime(self):
        return datetime_to_timezone(self.pub_datetime).replace(tzinfo=None)

    @property
    def local_updated(self):
        return datetime_to_timezone(self.updated).replace(tzinfo=None)

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
        instructions = parse(text).compile('html')
        return render(instructions, context)

    @property
    def rendered_text(self):
        if hasattr(self, '_rendered_text'):
            return self._rendered_text
        return self._render(self.text, 'ikhaya/article_text/%s' % self.id)

    @property
    def rendered_intro(self):
        if hasattr(self, '_rendered_intro'):
            return self._rendered_intro
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
        if action == 'comments':
            return href('ikhaya', stamp, self.slug, _anchor='comments')
        return href(*{
            'show': ('ikhaya', stamp, self.slug),
            'edit': ('admin', 'ikhaya', 'articles', 'edit', self.id),
            'delete': ('admin', 'ikhaya', 'articles', 'delete', self.id),
            'id': ( 'portal', 'ikhaya',  self.id)
        }[action])

    @property
    def checksum(self):
        return md5(''.join(x.encode('utf8') for x in
            (self.subject, self.intro, self.text))).hexdigest()

    def __unicode__(self):
        return u'%s - %s' % (
            self.pub_date.strftime('%d.%m.%Y'),
            self.subject
        )

    def __repr__(self):
        return '<%s %s - %s>' % (
            self.__class__.__name__,
            self.pub_date.strftime('%d.%m.%Y'),
            self.subject.encode('utf-8')
        )

    def update_search(self):
        """
        This updates the xapian search index.
        """
        IkhayaSearchAdapter.queue(self.id)

    def save(self, force_insert=False, force_update=False):
        """
        This increases the edit count by 1 and updates the xapian database.
        """
        if self.text is None or self.intro is None:
            # might happen, because cached objects are setting text and
            # intro to None to save some space
            raise ValueError(u'text and intro must not be null')
        suffix_id = False
        if not self.updated or self.updated < self.pub_datetime:
            self.updated = self.pub_datetime

        if not self.slug:
            self.slug = find_next_django_increment(Article, 'slug',
                slugify(self.subject), pub_date=self.pub_date)

        if not self.icon:
            # use the category's icon if available
            self.icon = self.category.icon

        # Force to use a valid slug
        slugified = slugify(self.slug)
        if slugified != self.slug:
            self.slug = slugified

        super(Article, self).save(force_insert, force_update)
        self.update_search()

        # now that we have the article id we can put it into the slug
        if suffix_id:
            self.slug = '%s-%s' % (self.slug, self.id)
            cur = connection.cursor()
            cur.execute('''
                update ikhaya_article set slug = %s where id = %s
            ''', [self.slug, self.id])
        cache.delete('ikhaya/archive')
        cache.delete('ikhaya/short_archive')
        cache.delete('ikhaya/article_text/%s' % self.id)
        cache.delete('ikhaya/article_intro/%s' % self.id)
        cache.delete('ikhaya/simple_text/%s' % self.id)
        cache.delete('ikhaya/simple_intro/%s' % self.id)
        cache.delete('ikhaya/article/%s' % self.slug)

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
    notes = models.TextField()
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

    @property
    def rendered_notes(self):
        context = RenderContext(current_request)
        key = 'ikhaya/suggestion_notes/%s' % self.id
        instructions = cache.get(key)
        if instructions is None:
            instructions = parse(self.notes).compile('html')
            cache.set(key, instructions)
        return render(instructions, context)


class Comment(models.Model):
    article = models.ForeignKey(Article, null=True)
    text = models.TextField()
    author = models.ForeignKey(User)
    pub_date = models.DateTimeField()
    deleted = models.BooleanField(null=False, default=False)
    rendered_text = models.TextField()

    def get_absolute_url(self, action='show'):
        if action in ['hide', 'restore', 'edit']:
            return href('ikhaya', 'comment', self.id, action)
        stamp = self.article.pub_date.strftime('%Y/%m/%d')
        return href('ikhaya', stamp, self.article.slug,
                    _anchor='comment_%s' % self.article.comment_count)

    def save(self, force_insert=False, force_update=False):
        if self.id is None:
            Article.objects.filter(id=self.article.id) \
                .update(comment_count=models.F('comment_count')+1)
        context = RenderContext(current_request)
        node = parse(self.text, wiki_force_existing=False)
        self.rendered_text = node.render(context, 'html')
        super(Comment, self).save(force_insert, force_update)
        if self.id:
            cache.delete('ikhaya/comment/%d' % self.id)


class ArticleSearchAuthDecider(object):
    """Decides whether a user can display a search result or not."""

    def __init__(self, user):
        self.now = datetime.utcnow()
        self.priv = user.can('article_read')

    def __call__(self, auth):
        if not isinstance(auth[1], datetime):
            # this is a workaround for old data in search-index.
            auth = list(auth)
            auth[1] = datetime(auth[1].year, auth[1].month, auth[1].day)
            auth = tuple(auth)
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
            date=article.pub_datetime,
            auth=(article.hidden, article.pub_datetime),
            category=article.category.slug,
            text=[article.text, article.intro]
        )

    def extract_data(self, article):
        return {'title': article.subject,
                'user': article.author.username,
                'date': article.pub_datetime,
                'url': url_for(article),
                'component': u'Ikhaya',
                'group': article.category.name,
                'group_url': url_for(article.category),
                'highlight': True,
                'text': u'%s %s' % (article.simplified_intro,
                                    article.simplified_text),
                'hidden': article.hidden,
                'user_url': url_for(article.author)}

    def recv(self, docid):
        article = Article.objects.select_related(depth=1).get(id=docid)
        return self.extract_data(article)

    def recv_multi(self, docids):
        articles = Article.objects.select_related(depth=1).filter(id__in=docids)
        return [self.extract_data(article) for article in articles]

    def get_doc_ids(self):
        cur = connection.cursor()
        cur.execute('select id from ikhaya_article')
        for row in cur.fetchall():
            yield row[0]
        cur.close()


search.register(IkhayaSearchAdapter())
