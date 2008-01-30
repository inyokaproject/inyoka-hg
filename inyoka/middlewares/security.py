# -*- coding: utf-8 -*-
"""
    inyoka.middlewares.security
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    A middleware that does CSRF protection in a slightly saner manner
    than the django one.  Unlike the django one this uses hmac, calculates
    the key only if a form exists and won't touch responses that are
    created from generators.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
import re
import hmac
from django.conf import settings


form_re = re.compile(r'<form\s+.*?method=[\'"]post[\'"].*?>(?i)')


class SecurityMiddleware(object):

    def _make_token(self, request):
        h = hmac.new(settings.SECRET_KEY, str(request.session.session_key))
        h.update(request.META.get('HTTP_USER_AGENT', ''))
        return h.hexdigest()

    def process_request(self, request):
        if request.method == 'POST':
            csrf_token = self._make_token(request)
            try:
                submitted_token = request.POST['_form_token']
                if csrf_token != submitted_token:
                    raise ValueError()
            except (KeyError, ValueError):
                return self._abort_with_csrf_error()

    def process_response(self, request, response):
        if response['content-type'].startswith('text/html') and \
           response._is_string:
            token = []
            def add_csrf_field(match):
                if not token:
                    token.append(self._make_token(request))
                return match.group() + (
                    '<div style="display: none">'
                      '<input type="hidden" name="_form_token" value="%s" />'
                    '</div>' % token[0]
                )
            response.content = form_re.sub(add_csrf_field, response.content)
        return response
