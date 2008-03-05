# -*- coding: utf-8 -*-
"""
    inyoka.utils.urls
    ~~~~~~~~~~~~~~~~~

    This module implements unicode aware unicode functions.  It also allows
    to build urls for different subdomains using the `href` function.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
import cgi
from urlparse import urlparse
from inyoka.conf import settings
from werkzeug import import_string, url_encode, url_decode, url_quote, \
     url_quote_plus, url_fix


def href(_module='portal', *parts, **query):
    """Generates an internal URL for different subdomains."""
    anchor = query.pop('_anchor', None)
    module = import_string('inyoka.%s.urls' % _module)
    subdomain = settings.SUBDOMAIN_REVERSE_MAP[_module]
    append_slash = getattr(module, 'require_trailing_slash', True)
    path = '/'.join(url_quote(x) for x in parts if x is not None)

    return 'http://%s%s/%s%s%s%s' % (
        subdomain and subdomain + '.' or '',
        settings.BASE_DOMAIN_NAME,
        path,
        append_slash and path and not path.endswith('/') and '/' or '',
        query and '?' + url_encode(query) or '',
        anchor and '#' + url_quote_plus(anchor) or ''
    )


def url_for(obj, action=None):
    """Get the URL for an object."""
    if hasattr(obj, 'get_absolute_url'):
        if action:
            url = obj.get_absolute_url(action=action)
        else:
            url = obj.get_absolute_url()
    else:
        raise TypeError('type %r has no url' % obj.__class__)
    if not url.startswith('http://'):
        subdomain = settings.SUBDOMAIN_REVERSE_MAP['portal']
        url = 'http://%s%s%s' % (
            subdomain and subdomain + '.' or '',
            settings.BASE_DOMAIN_NAME,
            url
        )
    return url


def is_safe_domain(url):
    """Check whether `url` points to the same host as inyoka"""
    scheme, netloc = urlparse(url)[:2]
    if scheme not in ('http', 'https', 'ftp'):
        return False
    return ('.' + netloc).endswith('.' + settings.BASE_DOMAIN_NAME)


def get_query_string(url):
    """Return the query string of a url"""
    return urlparse(url)[4]
