# -*- coding: utf-8 -*-
"""
    inyoka.application
    ~~~~~~~~~~~~~~~~~~

    The main WSGI application.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from django.core.handlers.wsgi import WSGIHandler
from django.core import urlresolvers
from inyoka.conf import settings
from inyoka.utils.http import PageNotFound, DirectResponse, TemplateResponse
from inyoka.utils.logger import logger
from inyoka.utils.database import session
from werkzeug import SharedDataMiddleware, Response, get_host

# Open debug thread for now
import guppy.heapy.RM

_not_found = Response('Not Found', status=404)
core_exceptions = (SystemExit, KeyboardInterrupt)
try:
    core_exceptions += (GeneratorExit,)
except NameError:
    pass


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


class InyokaHandler(WSGIHandler):
    """
    Improved version of the django WSGI app without the exception handling
    which is somewhat annoying for our use case.
    """

    def get_response(self, request):
        """Like the normal one but faster and less sucky."""
        try:
            # Apply request middleware
            for middleware_method in self._request_middleware:
                response = middleware_method(request)
                if response:
                    return response

            try:
                # we've had the situation that there was no resolver.  In
                # theory that should never happen but if a middleware is
                # broken it may be the case.  in that case abort with 404
                resolver = getattr(request, 'resolver', None)
                if resolver is None:
                    raise PageNotFound()

                callback, args, kwargs = resolver.resolve(request.path)

                # Apply view middleware
                for middleware_method in self._view_middleware:
                    response = middleware_method(request, callback,
                                                 args, kwargs)
                    if response:
                        return response

                try:
                    return callback(request, *args, **kwargs)
                except Exception, e:
                    # If the view raised an exception, run it through
                    # exception middleware, and if the exception middleware
                    # returns a response, use that. Otherwise, reraise the
                    # exception.
                    for middleware_method in self._exception_middleware:
                        response = middleware_method(request, e)
                        if response:
                            return response
                    raise
            except PageNotFound, e:
                if resolver is None:
                    urlconf = getattr(request, "urlconf", settings.ROOT_URLCONF)
                    resolver = urlresolvers.RegexURLResolver(r'^/', urlconf)
                callback, param_dict = resolver.resolve404()
                return callback(request, **param_dict)
            except DirectResponse, e:
                return e.response
            except core_exceptions:
                raise
            except:
                if settings.DEBUG:
                    raise
                logger.exception('Exception during request at %r' %
                                 request.build_absolute_uri())
                return TemplateResponse('errors/500.html', {}, 500)
        finally:
            # remove the sqlalchemy session and rollback if not committed
            # yet.
            session.remove()


application = InyokaHandler()
