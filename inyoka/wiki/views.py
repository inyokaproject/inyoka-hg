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
from inyoka.utils.urls import href, is_safe_domain, url_for
from inyoka.utils.html import escape
from inyoka.utils.http import PageNotFound, HttpResponseRedirect
from inyoka.utils.flashing import flash
from inyoka.utils.http import templated, AccessDeniedResponse
from inyoka.wiki.models import Page
from inyoka.wiki.actions import PAGE_ACTIONS
from inyoka.wiki.utils import normalize_pagename, get_thumbnail, \
     pagename_join
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
        flash('Konnte Seite nicht erstellen, kein Seitenname angegeben '
              'wurde.', success=False)
        return HttpResponseRedirect(backref)
    if base:
        page = pagename_join(base, page)
    try:
        page = Page.objects.get(name=page)
    except Page.DoesNotExist:
        if template:
            options['template'] = pagename_join(settings.WIKI_TEMPLATE_BASE,
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
