# -*- coding: utf-8 -*-
"""
    inyoka.utils.urls
    ~~~~~~~~~~~~~~~~~

    This module implements unicode aware unicode functions.  It also allows
    to build urls for different subdomains using the `href` function.


    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import re
from urlparse import urlparse
from django.core.urlresolvers import RegexURLResolver
from inyoka.conf import settings
from werkzeug import import_string, url_encode, url_quote, url_quote_plus


# extended at runtime with module introspection information
_append_slash_map = {'static': False, 'media': False}
_url_reverse_map = dict((v.split('.')[1], k) for k, v in
                        settings.SUBDOMAIN_MAP.iteritems())
_resolvers = {}
_schema_re = re.compile(r'[a-z]+://')
acceptable_protocols = set([
    'ed2k', 'ftp', 'http', 'https', 'irc', 'mailto', 'news', 'gopher',
    'nntp', 'telnet', 'webcal', 'xmpp', 'callto', 'feed', 'urn',
    'aim', 'rsync', 'tag', 'ssh', 'sftp', 'rtsp', 'afs', 'git', 'msn'
])


def href(_module='portal', *parts, **query):
    """Generates an internal URL for different subdomains."""
    anchor = query.pop('_anchor', None)
    if _module not in _append_slash_map:
        module = import_string('inyoka.%s.urls' % _module)
        append_slash = getattr(module, 'require_trailing_slash', True)
        _append_slash_map[_module] = append_slash
    else:
        append_slash = _append_slash_map[_module]
    path = '/'.join(url_quote(x) for x in parts if x is not None)

    base_url = 'http://%s' % settings.BASE_DOMAIN_NAME
    if _module in ('media', 'static'):
        base_url = {
            'media': settings.MEDIA_URL,
            'static': settings.STATIC_URL,
        }[_module].rstrip('/')
    else:
        subdomain = _url_reverse_map[_module]
        base_url = 'http://%s%s' % (subdomain + '.' if subdomain else '', settings.BASE_DOMAIN_NAME)

    return '%s/%s%s%s%s' % (
        base_url,
        path,
        append_slash and path and not path.endswith('/') and '/' or '',
        query and '?' + url_encode(query) or '',
        anchor and '#' + url_quote_plus(anchor) or ''
    )


def url_for(obj, action=None, **kwargs):
    """
    Get the URL for an object.  As we are not using django contrib stuff
    any more this method is not useful any more but no it isn't because
    django does ugly things with `get_absolute_url` so we have to do that.
    """
    if hasattr(obj, 'get_absolute_url'):
        if action is not None:
            return obj.get_absolute_url(action, **kwargs)
        return obj.get_absolute_url(**kwargs)
    raise TypeError('type %r has no url' % obj.__class__)


def is_safe_domain(url):
    """Check whether `url` points to the same host as inyoka"""
    scheme, netloc = urlparse(url)[:2]
    if scheme not in acceptable_protocols:
        return False
    return ('.' + netloc).endswith('.' + settings.BASE_DOMAIN_NAME)


def is_external_target(location):
    """
    Check if a target points to an external URL or an internal page.  Returns
    `True` if the target is an external URL.
    """
    return _schema_re.match(location) is not None


def get_query_string(url):
    """Return the query string of a URL"""
    return urlparse(url)[4]


def get_path_info(url, charset='utf-8'):
    """Return the path info of a URL."""
    return urlparse(url)[2].decode(charset, 'utf-8', 'ignore')


def get_server_name(url, charset='utf-8'):
    """Return the server name for a URL."""
    return urlparse(url)[1].decode(charset, 'utf-8', 'ignore')


def get_resolver(host):
    """Get the subdomain and resolver for that server name or (None, None)."""
    if host.endswith(settings.BASE_DOMAIN_NAME):
        subdomain = host[:-len(settings.BASE_DOMAIN_NAME)].rstrip('.')
        if subdomain == 'www':
            return subdomain, None
        if subdomain in settings.SUBDOMAIN_MAP:
            name = settings.SUBDOMAIN_MAP[subdomain]
            if name not in _resolvers:
                _resolvers[name] = resolver = RegexURLResolver('^/', name)
            else:
                resolver = _resolvers[name]
            return subdomain, resolver
    return None, None


def clean_openid_url(url):
    """
    Normalizes according to (only URLs though, not XRI):
    http://openid.net/specs/openid-authentication-2_0.html#normalization_example
    """
    parts = urlparse(url)
    if parts.path == '':
        return url + '/'
    return url


from inyoka.utils.http import TemplateResponse
def global_not_found(request, app, err_message=None):
    return TemplateResponse('errors/404.html', {
        'err_message': err_message,
        'app': app,
    }, 404)
