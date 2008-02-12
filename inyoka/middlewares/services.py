# -*- coding: utf-8 -*-
"""
    inyoka.middlewares.services
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Because of the same-origin policy we do not serve AJAX services as part
    of the normal, subdomain bound request dispatching. This middleware
    dispatches AJAX requests on every subdomain to the modules that provide
    JSON callbacks.

    What it does is listening for "/?__service__=wiki.something" which
    dispatches to ``inyoka.wiki.services.dispatcher('something')``.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from django.http import HttpResponse
from simplejson import dumps


JSON_CONTENTTYPE = 'application/json'


class ServiceMiddleware(object):

    def process_request(self, request):
        if request.path == '/' and '__service__' in request.GET:
            parts = request.GET['__service__'].split('.', 1)
            response = None
            if len(parts) == 2 and parts[0] not in ('middlewares', 'utils'):
                try:
                    call = __import__('inyoka.%s.services' % parts[0], None,
                                      None, ['dispatcher']).dispatcher
                except (ImportError, AttributeError), e:
                    pass
                else:
                    response = call(request, parts[1])
            if isinstance(response, HttpResponse):
                return response
            json = dumps(response, encoding='utf-8')
            return HttpResponse(json, content_type=JSON_CONTENTTYPE)
