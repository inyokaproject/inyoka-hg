# -*- coding: utf-8 -*-
"""
    inyoka.wiki.views
    ~~~~~~~~~~~~~~~~~

    The views for the wiki. Unlike the other applications the wiki doesn't
    really use the views but `actions`. This is the case because we only
    have one kind of page which is a wiki page. Non existing pages render
    a replacement message to create one, so not much to dispatch.

    Some internal functions such as the image serving are implemented as
    views too because they do not necessarily work on page objects.


    :copyright: Copyright 2007 by Armin Ronacher, Benjamin Wiegand.
    :license: GNU GPL.
"""
from urlparse import urljoin
from django.conf import settings
from django.http import HttpResponseRedirect, Http404 as PageNotFound
from inyoka.utils.urls import href
from inyoka.utils.http import templated, AccessDeniedResponse
from inyoka.wiki.models import Page
from inyoka.wiki.actions import PAGE_ACTIONS
from inyoka.wiki.utils import normalize_pagename, get_thumbnail, \
     is_external_target
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
    if action and action not in PAGE_ACTIONS:
        return missing_resource(request)
    return PAGE_ACTIONS[action or 'show'](request, normalized_name)


@templated('wiki/missing_resource.html', status=404)
def missing_resource(request):
    """
    Called if the templated decorator catches a `ObjectDoesNotExist`
    exception on the wiki. This does not affect missing pages
    because the show view checks for that.

    **Template**
        ``'wiki/missing_resource.html'``

    **Context**
        none

    Not having a context doesn't mean that a template cannot render
    something. The default context objects also exists for this one.
    """


def get_image_resource(request):
    """
    Deliver the attachment or external URL as image. This is used by the
    `Picture` macro mainly. The idea is that we can still check privileges
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

    if not is_external_target(target):
        target = normalize_pagename(target)
        if not has_privilege(request.user, target, 'read'):
            return AccessDeniedResponse()

    if height or width:
        target = urljoin(settings.MEDIA_URL,
                         get_thumbnail(target, width, height,
                                       request.GET.get('force') == 'yes'))
    elif not is_external_target(target):
        target = Page.objects.attachment_for_page(target)
        target = href('media', target)
    if not target:
        raise PageNotFound()
    return HttpResponseRedirect(target)
