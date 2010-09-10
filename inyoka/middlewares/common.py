# -*- coding: utf-8 -*-
"""
    inyoka.middlewares.common
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    This module provides a middleware that sets the url conf for the current
    request depending on the site we are working on and does some more common
    stuff like session updating.

    This middleware replaces the common middleware.

    For development purposes we also set up virtual url dispatching modules for
    static and media.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import re
from django.db import connection
from django.middleware.common import CommonMiddleware
from inyoka import INYOKA_REVISION
from inyoka.conf import settings
from inyoka.utils.http import HttpResponsePermanentRedirect, HttpResponseForbidden
from inyoka.utils.urls import get_resolver
from inyoka.utils.database import session
from inyoka.utils.flashing import has_flashed_messages
from inyoka.utils.local import local, local_manager, request_cache
from inyoka.utils.timer import StopWatch
from inyoka.utils.debug import inject_query_info



re_htmlmime = re.compile(r'^text/x?html')


class CommonServicesMiddleware(CommonMiddleware):
    """Hook in as first middleware for common tasks."""

    def process_request(self, request):
        # check for disallowed user agents
        if 'HTTP_USER_AGENT' in request.META:
            for user_agent_regex in settings.DISALLOWED_USER_AGENTS:
                if user_agent_regex.search(request.META['HTTP_USER_AGENT']):
                    return HttpResponseForbidden('<h1>Forbidden</h1>')

        # populate the request
        local.request = request
        # create local cache object if it does not exist
        # (so that our cache is not overwriting it every time...)
        try:
            request_cache._get_current_object()
        except RuntimeError:
            local.cache = {}

        if not hasattr(request, 'queries'):
            request.queries = []

        # Start time tracker
        request.watch = StopWatch()
        request.watch.start()

        # dispatch requests to subdomains or redirect to the portal if
        # it's a request to a unknown subdomain
        # redirect www.* to the equivalent without www.
        request.subdomain, resolver = get_resolver(request.get_host())

        if not resolver:
            if request.subdomain == 'www':
                url = 'http://%s%s' % (settings.BASE_DOMAIN_NAME,
                    request.get_full_path())
                return HttpResponsePermanentRedirect(url)
            main_url = 'http://%s/' % settings.BASE_DOMAIN_NAME
            return HttpResponsePermanentRedirect(main_url)

        # this is used by our dispatcher
        request.resolver = resolver

        # check trailing slash setting
        if getattr(resolver.urlconf_module, 'require_trailing_slash', True):
            if not request.path.endswith('/'):
                new_url = 'http://%s%s%s' % (
                    request.subdomain and request.subdomain + '.' or '',
                    settings.BASE_DOMAIN_NAME,
                    request.path + '/'
                )
                if request.GET:
                    new_url += '?' + request.GET.urlencode()
                return HttpResponsePermanentRedirect(new_url)

    def process_response(self, request, response):
        """
        Hook our X-Powered header in (and an easteregg header).  And clean up
        the werkzeug local.
        """
        # XXX: move this to the connection-builder
        response = CommonMiddleware.process_response(self, request, response)
        powered_by = 'Inyoka'
        if INYOKA_REVISION:
            powered_by += '/rev-%s' % INYOKA_REVISION
        response['X-Powered-By'] = powered_by
        response['X-Philosophy'] = 'Don\'t be hasty, open a ticket, get some holiday and let us relax. We\'re on it.'

        # update the cache control
        if hasattr(request, 'user') and request.user.is_authenticated \
           or has_flashed_messages():
            response['Cache-Control'] = 'no-cache'

        path = request.path
        excludes = ('.js', '.css')
        exclude = any(x in path for x in excludes)
        if settings.DEBUG and not exclude and not '__service__' in request.GET:
            inject_query_info(request, response)

        # clean up after the local manager
        local_manager.cleanup()
        session.remove()

        return response


# import all application modules so that we get bootstrapping
# code executed. (in the apps __init__.py file)
_app = None
for _app in settings.INSTALLED_APPS:
    __import__(_app)
del _app
