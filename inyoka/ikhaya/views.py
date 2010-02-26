# -*- coding: utf-8 -*-
"""
    inyoka.ikhaya.views
    ~~~~~~~~~~~~~~~~~~~

    Views for Ikhaya.

    :copyright: 2007 - 2008 by Benjamin Wiegand, Christoph Hack.
    :license: GNU GPL, see LICENSE for more details.
"""
from datetime import datetime, date
from django.utils.text import truncate_html_words
from django.db.models import Q
from inyoka.utils.urls import href, url_for, global_not_found
from inyoka.utils.http import templated, AccessDeniedResponse, \
     HttpResponseRedirect, HttpResponse, PageNotFound, \
     does_not_exist_is_404
from inyoka.utils.html import escape
from inyoka.utils.feeds import FeedBuilder, atom_feed
from inyoka.utils.flashing import flash
from inyoka.utils.pagination import Pagination
from inyoka.utils.cache import cache
from inyoka.utils.dates import MONTHS
from inyoka.utils.sessions import set_session_info
from inyoka.utils.templating import render_template
from inyoka.utils.notification import send_notification
from inyoka.portal.utils import check_login, require_permission
from inyoka.portal.user import User
from inyoka.ikhaya.forms import SuggestArticleForm, EditCommentForm
from inyoka.ikhaya.models import Category, Article, Suggestion, Comment
from inyoka.wiki.parser import parse, RenderContext


IKHAYA_DESCRIPTION = u'Ikhaya ist der Nachrichtenblog der ubuntuusers-' \
    u'Community. Hier werden Nachrichten und Berichte rund um Ubuntu, Linux' \
    u' und OpenSource-Software veröffentlicht.'

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
        link = (year, month)
    elif category_slug:
        category = Category.objects.get(slug=category_slug)
        articles = category.article_set.all()
        link = ('category', category_slug)
    else:
        articles = Article.objects.all()
        link = ()

    if not request.user.can('article_read'):
        articles = articles.filter(public=True) \
                           .filter(Q(pub_date__lt=datetime.utcnow().date())|
                                   Q(pub_date = datetime.utcnow().date(), pub_time__lte = datetime.utcnow().time()))

    link = href('ikhaya', *link)
    set_session_info(request, u'sieht sich die <a href="%s">'
                              u'Artikelübersicht</a> an' % link)

    articles = articles.order_by('public', '-updated').select_related()

    pagination = Pagination(request, articles, page, 15, link)

    return {
        'articles':      list(pagination.objects),
        'pagination':    pagination,
        'category':      category
    }


@templated('ikhaya/detail.html', modifier=context_modifier)
def detail(request, year, month, day, slug):
    """Shows a single article."""
    article = Article.objects.select_related().get(
        pub_date=date(int(year), int(month), int(day)),
        slug=slug)
    preview = None
    if article.hidden or article.pub_datetime > datetime.utcnow():
        if not request.user.can('article_read'):
            return AccessDeniedResponse()
        flash(u'Dieser Artikel ist für reguläre Benutzer nicht sichtbar.')
    else:
        set_session_info(request, u'sieht sich den Artikel „<a href="%s">%s'
                         u'</a>“' % (url_for(article), escape(article.subject)))
    if article.comments_enabled and request.method == 'POST':
        form = EditCommentForm(request.POST)
        if 'preview' in request.POST:
            ctx = RenderContext(request)
            preview = parse(request.POST.get('text', '')).render(ctx, 'html')
        elif form.is_valid():
            data = form.cleaned_data
            if data.get('comment_id') and request.user.can('comment_edit'):
                c = Comment.objects.get(id=data['comment_id'])
                c.text = data['text']
                flash(u'Das Kommentar wurde erfolgreich bearbeitet.', True)
            else:
                c = Comment(text=data['text'])
                c.article = article
                c.author = request.user
                c.pub_date = datetime.utcnow()
                flash(u'Dein Kommentar wurde erstellt.', True)
            c.save()
            return HttpResponseRedirect(url_for(article))
    elif request.GET.get('moderate'):
        comment = Comment.objects.get(id=int(request.GET.get('moderate')))
        form = EditCommentForm(initial={
            'comment_id':   comment.id,
            'text':         comment.text,
        })
    else:
        form = EditCommentForm()
    return {
        'article':  article,
        'comments': list(article.comment_set.select_related()),
        'form': form,
        'preview': preview,
        'can_post_comment': request.user.is_authenticated,
        'can_admin_comment': request.user.can('comment_edit'),
        'can_edit_article': request.user.can('article_edit'),
    }


def change_comment(boolean, text):
    @require_permission('comment_edit')
    def do(request, comment_id):
        c = Comment.objects.get(id=comment_id)
        c.deleted = boolean
        c.save()
        flash(text, True)
        return HttpResponseRedirect(url_for(c))
    return do

hide_comment = change_comment(True, u'Der Kommentar wurde verborgen.')
restore_comment = change_comment(False, u'Der Kommentar wurde wiederhergestellt.')


@require_permission('comment_edit')
@templated('ikhaya/edit_comment.html')
def edit_comment(request, comment_id):
    comment = Comment.objects.get(id=comment_id)
    if request.method == 'POST':
        form = EditCommentForm(request.POST)
        if form.is_valid():
            comment.text = form.cleaned_data['text']
            comment.save()
            flash('Der Kommentar wurde gespeichert', True)
            return HttpResponseRedirect(comment.get_absolute_url())
    else:
        form = EditCommentForm(initial={'text': comment.text})
    return {
        'comment':  comment,
        'form':     form,
    }


@templated('ikhaya/archive.html', modifier=context_modifier)
def archive(request):
    """Shows the archive index."""
    set_session_info(request, u'sieht sich das <a href="%s">Archiv</a> an' %
                     href('ikhaya', 'archive'))
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
            Suggestion(author=request.user, pub_date=datetime.utcnow(),
                       title=d['title'], text=d['text'], intro=d['intro'],
                       notes=d['notes']).save()
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


@require_permission('article_edit')
@templated('ikhaya/suggestionlist.html')
def suggestionlist(request):
    """Get a list of all reported topics"""
    suggestions = Suggestion.objects.all()
    return {
        'suggestions': list(suggestions)
    }

@require_permission('article_edit')
def suggestion_delete(request, suggestion):
    if request.method == 'POST':
        if not 'cancel' in request.POST:
            try:
                s = Suggestion.objects.get(id=suggestion)
            except Suggestion.DoesNotExist:
                flash('Diesen Vorschlag gibt es nicht.', False)
                return HttpResponseRedirect(href('ikhaya', 'suggestions'))
            if request.POST.get('note'):
                args = {
                    'title':    s.title,
                    'username': request.user.username,
                    'note':     request.POST['note']
                }
                send_notification(s.author, u'suggestion_rejected',
                    u'Ikhaya-Vorschlag gelöscht', args)
            cache.delete('ikhaya/suggestion_count')
            s.delete()
            flash(u'Der Vorschlag wurde gelöscht.', True)
        else:
            flash(u'Der Vorschlag wurde nicht gelöscht.')
        return HttpResponseRedirect(href('ikhaya', 'suggestions'))
    else:
        try:
            s = Suggestion.objects.get(id=suggestion)
        except Suggestion.DoesNotExist:
            flash('Diesen Vorschlag gibt es nicht.', False)
            return HttpResponseRedirect(href('ikhaya', 'suggestions'))
        flash(render_template('ikhaya/delete_suggestion.html',
              {'s': s}))
        return HttpResponseRedirect(href('ikhaya', 'suggestions'))

def suggestion_assign_to(request, suggestion, username):
    suggestion = Suggestion.objects.get(id=suggestion)
    if username == '-':
        suggestion.owner = None
        suggestion.save()
        flash(u'Der Vorschlag wurde niemand zugewiesen', True)
    else:
        try:
            suggestion.owner = User.objects.get(username)
        except User.DoesNotExist:
            raise PageNotFound
        suggestion.save()
        flash(u'Der Vorschlag wurde %s zugewiesen' % username, True)
    return HttpResponseRedirect(href('ikhaya', 'suggestions'))


@atom_feed('ikhaya/feeds/articles/%(slug)s/%(mode)s/%(count)s')
def article_feed(request, slug=None, mode='short', count=20):
    """
    Shows the ikhaya entries that match the given criteria in an atom feed.
    """
    articles = Article.published.order_by('-updated').select_related()

    if slug:
        articles = articles.filter(category__slug=slug)
        title = u'ubuntuusers Ikhaya – %s' % slug
        url = href('ikhaya', 'category', slug)
    else:
        title = u'ubuntuusers Ikhaya'
        url = href('ikhaya')

    feed = FeedBuilder(
        subtitle=IKHAYA_DESCRIPTION,
        rights=href('portal', 'lizenz'),
        feed_url=request.build_absolute_uri(),
        id=url,
        url=url,
        title=title,
        icon=href('static', 'img', 'favicon.png'),
    )

    for article in articles[:count]:
        kwargs = {}
        if mode == 'full':
            kwargs['content'] = u'%s\n%s' % (article.rendered_intro,
                                             article.rendered_text)
            kwargs['content_type'] = 'xhtml'
        if mode == 'short':
            kwargs['summary'] = article.rendered_intro
            kwargs['summary_type'] = 'xhtml'

        feed.add(
            title=article.subject,
            url=url_for(article),
            updated=article.updated,
            published=article.pub_datetime,
            author={
                'name': article.author.username,
                'uri':  url_for(article.author)
            },
            **kwargs
        )
    return feed


@atom_feed('ikhaya/feeds/comments/%(id)s/%(mode)s/%(count)s')
@does_not_exist_is_404
def comment_feed(request, id=None, mode='short', count=20):
    """
    Shows the ikhaya comments that match the given criteria in an atom feed.
    """
    comments = Comment.objects.select_related().filter(article__public=True) \
                      .order_by('-id')
    if id:
        article = Article.published.get(id=id)
        comments = comments.filter(article=article.id)
        title = u'ubuntuusers Ikhaya-Kommentare – %s' % article.subject
        url = url_for(article)
    else:
        title = u'ubuntuusers Ikhaya-Kommentare'
        url = href('ikhaya')

    feed = FeedBuilder(
        subtitle=IKHAYA_DESCRIPTION,
        rights=href('portal', 'lizenz'),
        feed_url=request.build_absolute_uri(),
        id=url,
        url=url,
        title=title,
        icon=href('static', 'img', 'favicon.ico'),
    )

    for comment in comments[:count]:
        kwargs = {}
        if mode == 'full':
            kwargs['content'] = comment.rendered_text
            kwargs['content_type'] = 'xhtml'
        if mode == 'short':
            kwargs['summary'] = truncate_html_words(comment.rendered_text, 100)
            kwargs['summary_type'] = 'xhtml'

        feed.add(
            title=u'Re: %s' % comment.article.subject,
            url=url_for(comment),
            updated=comment.pub_date,
            published=comment.pub_date,
            author={
                'name': comment.author.username,
                'uri':  url_for(comment.author)
            },
            **kwargs
        )
    return feed
