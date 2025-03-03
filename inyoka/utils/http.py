# -*- coding: utf-8 -*-
"""
    inyoka.utils.http
    ~~~~~~~~~~~~~~~~~

    This module contains functions for http-related things like special
    responses etc.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from django.http import HttpResponse, HttpResponseRedirect, \
     HttpResponsePermanentRedirect, HttpResponseForbidden, \
     Http404 as PageNotFound
from django.core.exceptions import ObjectDoesNotExist
from sqlalchemy.orm.exc import NoResultFound
from inyoka.conf import settings
from inyoka.utils.decorators import patch_wrapper


def templated(template_name, status=None, modifier=None,
              content_type='text/html; charset=utf-8'):
    """
    This function can be used as a decorator to use a function's return value
    as template context if it's not a valid Response object.
    The first decorator argument should be the name of the template to use::

        @templated('mytemplate.html')
        def foo(req):
            return {
                'foo': 'bar'
            }

    `ObjectNotFound` exceptions are catched and raised again as
    `PageNotFound`.
    """
    def decorator(f):
        def proxy(request, *args, **kwargs):
            try:
                rv = f(request, *args, **kwargs)
            except (ObjectDoesNotExist, NoResultFound):
                raise PageNotFound()
            if isinstance(rv, HttpResponse):
                return rv
            elif rv is None:
                rv = {}
            if modifier is not None:
                modifier(request, rv)
            return TemplateResponse(template_name, rv, status=status,
                                    content_type=content_type)
        return patch_wrapper(proxy, f)
    return decorator


def does_not_exist_is_404(f):
    """For untemplated pages a `DoesNotExist` to `404`."""
    def proxy(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except (ObjectDoesNotExist, NoResultFound):
            raise PageNotFound()
    return patch_wrapper(proxy, f)


class TemplateResponse(HttpResponse):
    """
    Returns a rendered template as response.
    """
    def __init__(self, template_name, context, status=200,
                 content_type='text/html; charset=utf-8'):
        if settings.DEBUG:
            self.tmpl_context = context
        tmpl = render_template(template_name, context)
        HttpResponse.__init__(self, tmpl, status=status,
                              content_type=content_type)


class AccessDeniedResponse(TemplateResponse):
    """
    Returns an error message that the user has not enough rights.
    """
    def __init__(self):
        TemplateResponse.__init__(self, 'errors/403.html', {}, status=403)


class DirectResponse(Exception):

    def __init__(self, response):
        Exception.__init__(self, response)
        self.message = 'direct response %r' % response
        self.response = response


# circular import
from inyoka.utils.templating import render_template
