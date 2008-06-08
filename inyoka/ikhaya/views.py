# -*- coding: utf-8 -*-
"""
    inyoka.ikhaya.views
    ~~~~~~~~~~~~~~~~~~~

    Views for Ikhaya.

    :copyright: 2007 by Benjamin Wiegand, Christoph Hack.
    :license: GNU GPL, see LICENSE for more details.
"""
from datetime import datetime
from inyoka.portal.utils import check_login
from inyoka.portal.user import User
from inyoka.utils.urls import href, url_for, global_not_found
from inyoka.utils.http import templated, AccessDeniedResponse, \
     HttpResponseRedirect, HttpResponse, PageNotFound
from inyoka.utils.html import escape
from inyoka.utils.feeds import FeedBuilder
from inyoka.utils.flashing import flash
from inyoka.utils.pagination import Pagination
from inyoka.utils.cache import cache
from inyoka.utils.dates import MONTHS
from inyoka.utils.templating import render_template
from inyoka.utils.notification import send_notification
from inyoka.ikhaya.forms import SuggestArticleForm, EditCommentForm
from inyoka.ikhaya.models import Category, Article, Suggestion, Comment
from inyoka.wiki.parser import parse, RenderContext


def not_found(request, err_message=None):
    """
    This is called if no URL matches or a view returned a `PageNotFound`.
    """
    from inyoka.ikhaya.legacyurls import test_legacy_url
    response = test_legacy_url(request)
    if response is not None:
        return response
    return global_not_found(request, 'ikhaya', err_message)


def context_modifier(request, context):
    """
    This function adds two things to the context of all ikhaya pages:
    `archive`
        A list of the latest months with ikhaya articles.
    `categories`
        A list of all ikhaya categories.
    """
    key = 'ikhaya/archive'
    data = cache.get(key)
    if data is None:
        archive = list(Article.objects.dates('pub_date', 'month', order='DESC'))
        if len(archive) > 5:
            archive = archive[:5]
            short_archive = True
        else:
            short_archive = False
        data = {
            'archive':       archive,
            'short_archive': short_archive
        }
        cache.set(key, data)

    categories = cache.get('ikhaya/categories')
    if categories is None:
        categories = list(Category.objects.all())
        cache.set('ikhaya/categories', categories)

    context.update(
        MONTHS=dict(enumerate([''] + MONTHS)),
        categories=categories,
        **data
    )


@templated('ikhaya/index.html', modifier=context_modifier)
def index(request, year=None, month=None, category_slug=None, page=1):
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

    if not request.user.is_ikhaya_writer:
        articles = articles.filter(pub_date__lte=datetime.utcnow(),
                                   public=True)

    articles = articles.order_by('-pub_date').select_related()

    link = href('ikhaya', *link)
    pagination = Pagination(request, articles, page, 15, link)

    return {
        'articles':      list(pagination.objects),
        'pagination':    pagination,
        'category':      category
    }


@templated('ikhaya/detail.html', modifier=context_modifier)
def detail(request, slug):
    """Shows a single article."""
    article = Article.objects.select_related().get(slug=slug)
    preview = None
    if article.hidden or article.pub_date > datetime.utcnow():
        if not request.user.is_ikhaya_writer:
            return AccessDeniedResponse()
        flash(u'Dieser Artikel ist für reguläre Benutzer nicht sichtbar.')
    if article.comments_enabled and request.method == 'POST':
        form = EditCommentForm(request.POST)
        if 'preview' in request.POST:
            ctx = RenderContext(request)
            preview = parse(request.POST.get('text', '')).render(ctx, 'html')
        elif form.is_valid():
            data = form.cleaned_data
            c = Comment(**data)
            c.article = article
            c.author = request.user
            c.pub_date = datetime.utcnow()
            c.save()
            flash(u'Der Kommentar „%s“ wurde erstellt.' % escape(c.title))
            return HttpResponseRedirect(url_for(article))
    else:
        form = EditCommentForm()
    return {
        'article':  article,
        'comments': list(article.comment_set.select_related()),
        'form': form,
        'preview': preview
    }


@templated('ikhaya/archive.html', modifier=context_modifier)
def archive(request):
    """Shows the archive index."""
    months = Article.published.dates('pub_date', 'month')
    return {
        'months': months
    }


@check_login(message=u'Bitte melde dich an, um einen Ikhaya-Artikel '
                     u'vorzuschlagen.')
@templated('ikhaya/suggest.html', modifier=context_modifier)
def suggest(request):
    """
    A Page to suggest a new ikhaya article.  It just sends an email to the
    ikhaya administrators.
    """
    if request.method == 'POST':
        form = SuggestArticleForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            Suggestion(author=request.user, pub_date=datetime.utcnow(), title=
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
        if request.method == 'POST':
            if not 'cancel' in request.POST:
                s = Suggestion.objects.get(id=request.GET['delete'])
                if request.POST.get('note'):
                    text = render_template('mails/suggestion_rejected.txt', {
                        'title':    s.title,
                        'username': request.user.username,
                        'note':     request.POST['note']
                    })
                    send_notification(s.author, u'Ikhaya-Vorschlag abgelehnt',
                                      text)
                cache.delete('ikhaya/suggestion_count')
                s.delete()
                flash(u'Der Vorschlag wurde gelöscht.', True)
            else:
                flash(u'Der Vorschlag wurde nicht gelöscht.')
        else:
            flash(render_template('ikhaya/delete_suggestion.html',
                  {'s': Suggestion.objects.get(id=request.GET['delete'])}))
    return {
        'suggestions': list(suggestions)
    }

def suggestion_assign_to(request, suggestion, username):
    suggestion = Suggestion.objects.get(id=suggestion)
    if username == '-':
        suggestion.owner = None
        suggestion.save()
        flash(u'Der Vorschlag wurde niemand zugewiesen', True)
    else:
        try:
            suggestion.owner = User.objects.get(username=username)
        except User.DoesNotExist:
            raise PageNotFound
        suggestion.save()
        flash(u'Der Vorschlag wurde %s zugewiesen' % username, True)
    return HttpResponseRedirect(href('ikhaya', 'suggestions'))


def feed(request, category_slug=None, mode='short', count=20):
    """
    Shows the ikhaya entries that match the given criteria in an atom feed.
    """

    if not mode in ('full', 'short', 'title'):
        raise PageNotFound()

    count = int(count)
    if count not in (10, 20, 30, 50, 75, 100):
        raise PageNotFound()

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
