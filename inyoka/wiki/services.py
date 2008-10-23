# -*- coding: utf-8 -*-
"""
    inyoka.wiki.services
    ~~~~~~~~~~~~~~~~~~~~

    Because of the same-origin policy we do not serve AJAX services as part
    of the normal, subdomain bound request dispatching.  This middleware
    dispatches AJAX requests on every subdomain to the modules that provide
    JSON callbacks.

    What it does is listening for "/?__service__=wiki.something" which
    dispatches to ``inyoka.wiki.services.dispatcher('something')``.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from inyoka.utils.http import HttpResponse
from inyoka.utils.services import SimpleDispatcher
from inyoka.wiki.utils import get_smilies
from inyoka.wiki.parser import parse, RenderContext
from inyoka.wiki.models import Page


def on_get_smilies(request):
    """Get a list of smilies"""
    return get_smilies()


def on_render_preview(request):
    """Render some preview text."""
    page = None
    if 'page' in request.REQUEST:
        try:
            page = Page.objects.get_by_name(request.REQUEST['page'])
        except Page.DoesNotExist:
            page = None
    context = RenderContext(request, page)
    html = parse(request.REQUEST.get('text', '')).render(context, 'html')
    return HttpResponse(html)


dispatcher = SimpleDispatcher(
    get_smilies=on_get_smilies,
    render_preview=on_render_preview
)
