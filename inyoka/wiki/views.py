# -*- coding: utf-8 -*-
"""
    inyoka.wiki.views
    ~~~~~~~~~~~~~~~~~

    The views for the wiki.  Unlike the other applications the wiki doesn't
    really use the views but `actions`.  This is the case because we only
    have one kind of page which is a wiki page.  Non existing pages render
    a replacement message to create one, so not much to dispatch.

    Some internal functions such as the image serving are implemented as
    views too because they do not necessarily work on page objects.


    :copyright: Copyright 2007 by Armin Ronacher, Benjamin Wiegand.
    :license: GNU GPL.
"""
from urlparse import urljoin
from inyoka.conf import settings
from inyoka.utils.html import escape
from inyoka.utils.urls import href, is_safe_domain, url_for
from inyoka.utils.text import join_pagename, normalize_pagename
from inyoka.utils.http import templated, PageNotFound, HttpResponseRedirect, \
    AccessDeniedResponse
from inyoka.utils.cache import cache
from inyoka.utils.dates import format_datetime
from inyoka.utils.feeds import FeedBuilder
from inyoka.utils.flashing import flash
from inyoka.wiki.models import Page, Revision
from inyoka.wiki.actions import PAGE_ACTIONS
from inyoka.wiki.utils import get_thumbnail
from inyoka.wiki.acl import has_privilege


def index(request):
    """Wiki index is a redirect to the `settings.WIKI_MAIN_PAGE`."""
    return HttpResponseRedirect(
        href('wiki', settings.WIKI_MAIN_PAGE) +
        (request.GET and '?' + request.GET.urlencode() or '')
    )


def show_page(request, name):
    """Dispatch action calls."""
    normalized_name = normalize_pagename(name)
    if not normalized_name:
        return missing_resource(request, name)
    action = request.GET.get('action')
    if normalized_name != name or action == 'show':
        args = request.GET.copy()
        if action == 'show':
            del args['action']
        url = href('wiki', normalized_name)
        if args:
            url += '?' + args.urlencode()
        return HttpResponseRedirect(url)
        #XXX: for redirect pages ?action=show should prevent redirect
    if action and action not in PAGE_ACTIONS:
        return missing_resource(request)
    return PAGE_ACTIONS[action or 'show'](request, normalized_name)


def redirect_new_page(request):
    """Helper for the `NewPage` macro."""
    template = request.GET.get('template')
    base = request.GET.get('base', '')
    page = request.GET.get('page', '')
    options = {'action': 'edit'}
    backref = request.META.get('HTTP_REFERER')
    if not backref or not is_safe_domain(backref):
        backref = href('wiki', settings.WIKI_MAIN_PAGE)

    if not page:
        flash(u'Konnte Seite nicht erstellen, kein Seitenname angegeben '
              'wurde.', success=False)
        return HttpResponseRedirect(backref)
    if base:
        page = join_pagename(base, page)
    try:
        page = Page.objects.get(name=page)
    except Page.DoesNotExist:
        if template:
            options['template'] = join_pagename(settings.WIKI_TEMPLATE_BASE,
                                                template)
        return HttpResponseRedirect(href('wiki', page, **options))
    flash(u'Eine Seite mit dem Namen „<a href="%s">%s</a>“existiert '
          u'bereits.' % (url_for(page), escape(page.name)), success=False)
    return HttpResponseRedirect(backref)


@templated('wiki/missing_resource.html', status=404)
def missing_resource(request):
    """
    Called if the templated decorator catches a `ObjectDoesNotExist`
    exception on the wiki.  This does not affect missing pages
    because the show view checks for that.

    **Template**
        ``'wiki/missing_resource.html'``

    **Context**
        none

    Not having a context doesn't mean that a template cannot render
    something.  The default context objects also exists for this one.
    """


def get_attachment(request):
    """
    Get an attachment directly and do privilege check.
    """
    target = request.GET.get('target')
    if not target:
        raise PageNotFound()

    target = normalize_pagename(target)
    if not has_privilege(request.user, target, 'read'):
        return AccessDeniedResponse()

    target = Page.objects.attachment_for_page(target)
    target = href('media', target)
    if not target:
        raise PageNotFound()
    return HttpResponseRedirect(target)


def get_image_resource(request):
    """
    Deliver the attachment  as image.  This is used by the `Picture` macro
    mainly.  The idea is that we can still check privileges
    and that the image URL does not change if a new revision is uploaded.
    """
    try:
        width = request.GET['width']
    except (KeyError, ValueError):
        width = None
    try:
        height = request.GET['height']
    except (KeyError, ValueError):
        height = None
    target = request.GET.get('target')
    if not target:
        raise PageNotFound()

    target = normalize_pagename(target)
    if not has_privilege(request.user, target, 'read'):
        return AccessDeniedResponse()

    if height or width:
        target = urljoin(settings.MEDIA_URL,
                         get_thumbnail(target, width, height,
                                       request.GET.get('force') == 'yes'))
    else:
        target = Page.objects.attachment_for_page(target)
        target = href('media', target)
    if not target:
        raise PageNotFound()
    return HttpResponseRedirect(target)


def feed(request, page_name=None, count=20):
    """
    Shows the wiki pages or all revisions of one page that match
    the given criteria in an atom feed.
    """

    count = int(count)
    if count not in (10, 20, 30, 50, 50, 75, 100):
        raise PageNotFound()

    key = 'wiki/feeds/%s/%s' % (page_name, count)
    content = cache.get(key)
    if content is not None:
        content_type = 'application/atom-xml; charset=utf-8'
        return HttpResponse(content, content_type=content_type)

    if page_name:
        feed = FeedBuilder(
            title=u'ubuntuusers Wiki – %s' % page_name,
            url=href('wiki', page_name),
            feed_url=request.build_absolute_uri(),
            id=href('wiki', page_name),
            rights=href('portal', 'lizenz'),
        )
    else:
        feed = FeedBuilder(
            title=u'ubuntuusers Wiki – Letzte Änderungen',
            url=href('wiki', u'Letzte_Änderungen'),
            feed_url=request.build_absolute_uri(),
            id=href('wiki', u'Letzte_Änderungen'),
            rights=href('portal', 'lizenz'),
        )

    revisions = Revision.objects.all()
    if page_name:
        revisions = revisions.filter(page__name=page_name)

    for rev in revisions[:count]:
        kwargs = {}
        text = (u'%s hat am %s den Wikiartikel „%s“ geändert.%s' % (
                rev.user or 'Ein anonymer Benutzer', rev.change_date,
                rev.page.name, rev.note and (u' Zusammenfassung: \n%s'
                                             % rev.note) \
                                        or ''))

        kwargs['summary'] = (u'<div xmlns="http://www.w3.org/1999/xhtml">'
                             u'%s</div>' % text)
        feed.add(
            title='%s (%s)' % (
                rev.user or 'Anonymous',
                format_datetime(rev.change_date),
            ),
            url=url_for(rev),
            author=rev.user or 'Anonymous',
            published=rev.change_date,
            updated=rev.change_date,
            **kwargs
        )

    response = feed.get_atom_response()
    cache.set(key, response.content, 600)
    return response
