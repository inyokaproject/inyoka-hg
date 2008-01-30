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
import sys
import new
from django.http import HttpResponsePermanentRedirect, \
     HttpResponseForbidden
from django.conf import settings
from django.conf.urls.defaults import patterns
from django.middleware.common import CommonMiddleware
from inyoka.utils import import_string, INYOKA_REVISION


# Set up virtual url modules for static and media
for name, item in [('static', settings.STATIC_ROOT),
                   ('media', settings.MEDIA_ROOT)]:
    sys.modules['inyoka.%s.urls' % name] = module = new.module(name)
    __import__('inyoka.%s' % name, None, None, ['urls']).urls = module
    module.urlpatterns = patterns('',
        (r'(?P<path>.*)$', 'django.views.static.serve', {
           'document_root': item
        })
    )
    module.require_trailing_slash = False


# hook in debug call function
if settings.DEBUG:
    from inyoka.utils import interact
    import __builtin__
    __builtin__.INTERACT = interact
    del __builtin__, interact


class CommonServicesMiddleware(CommonMiddleware):

    def process_request(self, request):
        # check for disallowed user agents
        if 'HTTP_USER_AGENT' in request.META:
            for user_agent_regex in settings.DISALLOWED_USER_AGENTS:
                if user_agent_regex.search(request.META['HTTP_USER_AGENT']):
                    return HttpResponseForbidden('<h1>Forbidden</h1>')

        # dispatch requests to subdomains
        host = request.get_host()
        request.subdomain = None
        if host.endswith(settings.BASE_DOMAIN_NAME):
            subdomain = host[:-len(settings.BASE_DOMAIN_NAME)].rstrip('.')
            if subdomain in settings.SUBDOMAIN_MAP:
                request.subdomain = subdomain
                request.urlconf = settings.SUBDOMAIN_MAP[subdomain]

        # redirect to the portal because unknown subdomain
        if request.subdomain is None:
            main_url = 'http://%s/' % settings.BASE_DOMAIN_NAME
            return HttpResponsePermanentRedirect(main_url)

        # check trailing slash setting
        urlconf = import_string(request.urlconf)
        if getattr(urlconf, 'require_trailing_slash', True):
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
        Hook our X-Powered header in. (and an easteregg header).
        """
        response = CommonMiddleware.process_response(self, request, response)
        if INYOKA_REVISION:
            powered_by = 'Inyoka/rev-%s' % INYOKA_REVISION
        else:
            powered_by = 'Inyoka'
        response['X-Powered-By'] = powered_by
        response['X-Sucks'] = 'PHP in any version'
        return response


# import all application modules so that we get bootstrapping
# code executed. (in the apps __init__.py file)
_app = None
for _app in settings.INSTALLED_APPS:
    __import__(_app)
del _app
