# -*- coding: utf-8 -*-
"""
    inyoka.ikhaya.views
    ~~~~~~~~~~~~~~~~~~~

    Views for Ikhaya.

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
from datetime import datetime
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from inyoka.portal.views import not_found as global_not_found
from inyoka.utils.urls import href
from inyoka.utils.http import templated
from inyoka.utils.feeds import FeedBuilder
from inyoka.utils.flashing import flash
from inyoka.utils.pagination import Pagination
from inyoka.utils.decorators import check_login
from inyoka.ikhaya.forms import SuggestArticleForm
from inyoka.ikhaya.models import Category, Article, Suggestion


def not_found(request, err_message=None):
    return global_not_found(request, err_message)


def context_modifier(request, context):
    """
    This function adds two things to the context of all ikhaya pages:
    `archive`
        A list of the latest months with ikhaya articles.
    `categories`
        A list of all ikhaya categories.
    """
    archive = list(Article.objects.dates('pub_date', 'month', order='DESC'))
    if len(archive) > 5:
        archive = archive[:5]
        short_archive = True
    else:
        short_archive = False
    context.update(
        archive=archive,
        short_archive=short_archive,
        categories=list(Category.objects.all())
    )


@templated('ikhaya/index.html', modifier=context_modifier)
def index(req, year=None, month=None, category_slug=None, page=1):
    """Shows a few articles by different criteria"""
    category = None
    if year and month:
        articles = Article.objects.filter(
            pub_date__year=year,
            pub_date__month=month
        )
        link = ('month', '%s-%s' % (year, month))
    elif category_slug:
        category = Category.objects.get(slug=category_slug)
        articles = category.article_set.all()
        link = ('category', category_slug)
    else:
        articles = Article.objects.all()
        link = ()

    if False:
        # normal users shouldn't see articles that aren't public or whose
        # pub_date is in the future
        articles = articles.filter(pub_date__lte=datetime.datetime.now(),
                                   public=True)

    articles = articles.order_by('-pub_date')

    link = href('ikhaya', *link)
    pagination = Pagination(articles, page, link, per_page=15)

    return {
        'articles':      list(pagination.get_objects()),
        'pagination':    pagination.generate(),
        'category':      category
    }


@templated('ikhaya/detail.html', modifier=context_modifier)
def detail(req, slug):
    """Shows a single article."""
    # XXX: do not show this article if the user doesn't have
    # some special ikhaya privileges
    article = Article.objects.get(slug=slug)
    if article.hidden:
        flash(u'Dieser Artikel ist für normale Benutzer nicht sichtbar.')
    return {
        'article':  article
    }


@templated('ikhaya/archive.html', modifier=context_modifier)
def archive(req):
    """Shows the archive index."""
    months = Article.published.dates('pub_date', 'month')
    return {
        'months': months
    }


@check_login(message=u'Bitte melde dich an, um einen Ikhaya-Artikel '
                     u'vorzuschlagen')
@templated('ikhaya/suggest.html', modifier=context_modifier)
def suggest(request):
    """
    A Page to suggest a new ikhaya article. It just sends an email to the
    ikhaya administrators.
    """
    if request.method == 'POST':
        form = SuggestArticleForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            Suggestion(author=request.user, pub_date=datetime.now(), title=
                       d['title'], text=d['text'], intro=d['intro']).save()
            cache.delete('ikhaya/suggestion_count')
            flash(u'Dein Artikelvorschlag wurde versendet, das Ikhaya-Team '
                  u'wird sich sobald wie möglich darum kümmern.',
                  success=True)
            return HttpResponseRedirect(href('ikhaya'))
    else:
        form = SuggestArticleForm()
    return {
        'form': form
    }


@templated('ikhaya/suggestionlist.html')
def suggestionlist(request):
    """Get a list of all reported topics"""
    suggestions = Suggestion.objects.all()
    if 'delete' in request.GET:
        Suggestion.objects.delete(request.GET['delete'])
    return {
        'suggestions': list(suggestions)
    }


def feed(request, category_slug=None, mode='short', count=25):
    """
    Shows the ikhaya entries that match the given criteria in an atom feed.
    """

    if not mode in ('full', 'short', 'title'):
        raise Http404

    count = int(count)
    if count not in (5, 10, 15, 20, 25, 50, 75, 100):
        raise Http404

    key = 'ikhaya/feeds/%s/%s/%s' % (category_slug, mode, count)
    content = cache.get(key)
    if content is not None:
        content_type='application/atom+xml; charset=utf-8'
        return HttpResponse(content, content_type=content_type)

    if category_slug:
        feed = FeedBuilder(
            title=u'ubuntuusers Ikhaya – %s' % category_slug,
            url=href('ikhaya', 'category', category_slug),
            feed_url=request.build_absolute_uri(),
            id=href('ikhaya', 'category', category_slug),
            subtitle=u'Ikhaya ist der Nachrichtenblog der '
                     u'ubuntuusers-Community. Hier werden Nachrichten und '
                     u'Berichte rund um Ubuntu, Linux und OpenSource-Software '
                     u'veröffentlicht.',
            rights=href('portal', 'lizenz'),
        )
    else:
        feed = FeedBuilder(
            title=u'ubuntuusers Ikhaya',
            url=href('ikhaya'),
            feed_url=request.build_absolute_uri(),
            id=href('ikhaya'),
            subtitle=u'Ikhaya ist der Nachrichtenblog der '
                     u'ubuntuusers-Community. Hier werden Nachrichten und '
                     u'Berichte rund um Ubuntu, Linux und OpenSource-Software '
                     u'veröffentlicht.',
            rights=href('portal', 'lizenz'),
        )

    articles = Article.published.all()
    if category_slug:
        articles = articles.filter(category__slug=category_slug)

    for article in articles[:count]:
        kwargs = {}
        if mode == 'full':
            kwargs['content'] = u'<div xmlns="http://www.w3.org/1999/' \
                                u'xhtml">%s\n%s</div>' % (
                                    article.intro,
                                    article.text
                                )
            kwargs['content_type'] = 'xhtml'
        if mode == 'short':
            kwargs['summary'] = u'<div xmlns="http://www.w3.org/1999/' \
                                u'xhtml">%s</div>' % article.intro
        kwargs['author'] = {
            'name': article.author.username,
            'uri':  article.author.get_absolute_url()
        }

        feed.add(
            title=article.subject,
            url=article.get_absolute_url(),
            updated=article.updated,
            published=article.pub_date,
            **kwargs
        )

    response = feed.get_atom_response()
    cache.set(key, response.content, 600)
    return response
