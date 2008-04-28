# -*- coding: utf-8 -*-
"""
    inyoka.middlewares.security
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    A middleware that does CSRF protection in a slightly saner manner
    than the django one.  Unlike the django one this uses hmac, calculates
    the key only if a form exists and won't touch responses that are
    created from generators.


    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import re
import hmac
import pickle
from inyoka.conf import settings
from inyoka.utils.http import TemplateResponse


form_re = re.compile(r'<form\s+.*?method=[\'"]post[\'"][^>]*?>(?is)')
FORWARD_THRESHOLD = 1024 * 1024


class SecurityMiddleware(object):

    def _make_token(self, request):
        # we can't use the session key here unfortunately because the
        # users without cookie will get a new session key every darn
        # request.  That also means that we lose a bit of security
        # here :-(
        salt = request.session.get('uid')
        h = hmac.new(settings.SECRET_KEY, str(salt))
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
                return TemplateResponse('errors/400_csrf.html', {}, 400)

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
