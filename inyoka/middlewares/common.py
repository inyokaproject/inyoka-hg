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

    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from time import time
from django.db import connection
from django.conf.urls.defaults import patterns
from django.middleware.common import CommonMiddleware
from inyoka import INYOKA_REVISION
from inyoka.conf import settings
from inyoka.utils.http import PageNotFound, DirectResponse, \
     TemplateResponse, HttpResponsePermanentRedirect, \
     HttpResponseForbidden
from inyoka.utils.logger import logger
from inyoka.utils.urls import get_resolver
from inyoka.utils.database import session


class CommonServicesMiddleware(CommonMiddleware):
    """Hook in as first middleware for common tasks."""

    def __init__(self):
        from inyoka.utils.local import local, local_manager
        self._local = local
        self._local_manager = local_manager

    def process_request(self, request):
        # check for disallowed user agents
        if 'HTTP_USER_AGENT' in request.META:
            for user_agent_regex in settings.DISALLOWED_USER_AGENTS:
                if user_agent_regex.search(request.META['HTTP_USER_AGENT']):
                    return HttpResponseForbidden('<h1>Forbidden</h1>')

        # populate the request
        self._local.request = request

        # dispatch requests to subdomains or redirect to the portal if
        # it's a request to a unknown subdomain
        request.subdomain, resolver = get_resolver(request.get_host())
        if not resolver:
            #print request.get_host()
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
        response['X-Sucks'] = 'PHP --- every version'

        # clean up after the local manager
        self._local_manager.cleanup()
        session.remove()

        if settings.DEBUG:
            import sys
            import re
            from pprint import pformat
            from textwrap import wrap
            from inyoka.utils.terminal import get_dimensions, FancyPrinter
            p = FancyPrinter(sys.stderr)
            comma_re = re.compile(r',(?=\S)')
            cols, rows = get_dimensions()

            p.bold << '=' * cols << '\n'
            p.red << 'DATABASE QUERIES (%s)\n' % len(connection.queries)
            p.bold << '-' * cols << '\n'
            for idx, q in enumerate(connection.queries):
                p.green << '%s%s:\n' % (idx and '\n' or '', q['time'])
                for line in wrap(comma_re.sub(', ', q['sql']), cols - 6):
                    p << '    %s\n' % line.rstrip()
            p.bold << '=' * cols << '\n'
        return response


# import all application modules so that we get bootstrapping
# code executed. (in the apps __init__.py file)
_app = None
for _app in settings.INSTALLED_APPS:
    __import__(_app)
del _app
