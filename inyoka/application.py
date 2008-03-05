# -*- coding: utf-8 -*-
"""
    inyoka.application
    ~~~~~~~~~~~~~~~~~~

    The main WSGI application.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from django.core.handlers.wsgi import WSGIHandler
from django.views import debug
from inyoka.conf import settings
from werkzeug import SharedDataMiddleware, Response, get_host


# monkey patch the django internal debugger away
def null_technical_500_response(request, exc_type, exc_value, tb):
    raise exc_type, exc_value, tb
debug.technical_500_response = null_technical_500_response


_not_found = Response('Not Found', status=404)


class StaticDomainHandler(object):
    """
    A middleware for the development server to serve static data.  This
    doesn't require installing fake modules like we did with django
    previously and we also don't have to query the user for static stuff
    in the development mode which helps debugging.
    """

    def __init__(self, app):
        self.app = app
        self.handlers = {
            'static':   SharedDataMiddleware(_not_found, {
                '/':    settings.STATIC_ROOT
            }),
            'media':    SharedDataMiddleware(_not_found, {
                '/':    settings.MEDIA_ROOT
            })
        }

    def __call__(self, environ, start_response):
        host = get_host(environ)
        if host and host.endswith(settings.BASE_DOMAIN_NAME):
            subdomain = host[:-len(settings.BASE_DOMAIN_NAME)].rstrip('.')
            if subdomain in self.handlers:
                return self.handlers[subdomain](environ, start_response)
        return self.app(environ, start_response)


application = WSGIHandler()
