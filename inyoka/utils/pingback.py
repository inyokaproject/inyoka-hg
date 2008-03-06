# -*- coding: utf-8 -*-
"""
    inyoka.utils.pingback
    ~~~~~~~~~~~~~~~~~~~~~

    `Pingback 1.0`_ implementation for inyoka.

    .. _Pingback 1.0: http://www.hixie.ch/specs/pingback/pingback-1.0

    This module is currently unused because we don't support anonymous
    comments in ikhaya on the model and so we can't store pingbacks
    properly.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import re
import urllib2
from xmlrpclib import ServerProxy, Fault
from urlparse import urlparse
from inyoka.utils import xmlrpc
from inyoka.utils.html import striptags, escape, unescape
from inyoka.utils.urls import is_safe_domain, get_resolver


_title_re = re.compile(r'<title>(.*?)</title>(?i)')
_pingback_re = re.compile(r'<link rel="pingback" href="([^"]+)" ?/?>(?i)')
_chunk_re = re.compile(r'\n\n|<(?:p|div|h\d)[^>]*>')


class PingbackError(Exception):
    """
    Raised if the remote server caused an exception while pingbacking.
    This is not raised if the pingback function is unable to locate a
    remote server.
    """

    def __init__(self, fault_code):
        self.fault_code = fault_code
        Exception.__init__(self, fault_code)

    @property
    def ignore_silently(self):
        return self.fault_code in (17, 33, 48, 49)

    @property
    def description(self):
        return {
            16: _('source URL does not exist'),
            17: _('The source URL does not contain a link to the target URL'),
            32: _('The specified target URI does not exist'),
            33: _('The specified target URI cannot be used as a target'),
            48: _('The pingback has already been registered'),
            49: _('Access Denied')
        }.get(self.fault_code, _('An unknown server error (%s) occoured') %
              self.fault_code)


def pingback(source_uri, target_uri):
    """
    Try to notify the server behind `target_uri` that `source_uri`
    points to `target_uri`.  If that fails an `PingbackError` is raised.
    """
    try:
        url = urllib2.urlopen(target_uri)
    except:
        return False

    try:
        pingback_uri = url.info()['X-Pingback']
    except KeyError:
        match = _pingback_re.search(url.read())
        if match is None:
            raise PingbackError(33)
        pingback_uri = unescape(match.group(1))
    rpc = ServerProxy(pingback_uri)
    try:
        return rpc.pingback.ping(source_uri, target_uri)
    except Fault, e:
        raise PingbackError(e.faultCode)
    except:
        raise PingbackError(32)


def handle_pingback_request(source_uri, target_uri):
    """
    This method is exported via XMLRPC as `pingback.ping` by the pingback
    API.
    """
    # we only accept pingbacks for links below our blog URL
    if not is_safe_domain(target_uri):
        raise Fault(32, 'The specified target URI does not exist.')
    parts = urlparse(target_uri)
    path_info = parts.path.decode('utf-8', 'replace')
    resolver, _ = get_request(parts.netloc)

    # next we check if the source URL does indeed exist
    try:
        url = urllib2.urlopen(source_uri)
    except:
        raise Fault(16, 'The source URI does not exist.')

    # now it's time to look up our url endpoint for the target uri.
    # if we have one we check if that endpoint is listening for pingbacks.
    rv = resolver.resolve(path_info)
    if rv is None:
        raise Fault(33, 'The specified target URI does not exist.')

    func, args, kwargs = rv
    pingback_handler = getattr(func, 'pingback_handler', None)

    if pingback_handler is None:
        raise Failt(33, 'The specified target URI does not accept pingbacks.')

    # the handler can still decide not to support pingbacks and return a
    # fault code and fault message as tuple.  otherwise none.
    rv = pingback_handler(current_request._get_current_object(),
                          url, target_uri, *args, **kwargs)
    if rv is not None:
        raise Fault(*rv)

    # return some debug info
    return u'\n'.join((
        'endpoint: %r',
        'values: %r',
        'path_info: %r',
        'source_uri: %s',
        'target_uri: %s',
        'handler: %r'
    )) % (endpoint, values, path_info, source_uri, target_uri,
          pingback_handler.__name__)


def get_excerpt(url_info, url_hint, body_limit=1024 * 512):
    """
    Get an excerpt from the given `url_info` (the object returned by
    `urllib2.urlopen` or a string for a URL).  `url_hint` is the URL which
    will be used as anchor for the excerpt.  The return value is a tuple
    in the form ``(title, body)``.  If one of the two items could not be
    calculated it will be `None`.
    """
    if isinstance(url_info, basestring):
        url_info = urllib2.urlopen(url_info)
    contents = url_info.read(body_limit)
    title_match = _title_re.search(contents)
    title = title_match and striptags(title_match.group(1)) or None

    link_re = re.compile(r'<a[^>]+?"\s*%s\s*"[^>]*>(.*?)</a>(?is)' %
                         re.escape(url_hint))
    for chunk in _chunk_re.split(contents):
        match = link_re.search(chunk)
        if not match:
            continue
        before = chunk[:match.start()]
        after = chunk[match.end():]
        raw_body = '%s\0%s' % (striptags(before).replace('\0', ''),
                               striptags(after).replace('\0', ''))
        body_match = re.compile(r'(?:^|\b)(.{0,120})\0(.{0,120})\b') \
                       .search(raw_body)
        if body_match:
            break
    else:
        return (title, None)

    before, after = body_match.groups()
    link_text = striptags(match.group(1))
    if len(link_text) > 60:
        link_text = link_text[:60] + u'…'

    bits = before.split()
    bits.append(link_text)
    bits.extend(after.split())
    return title, u'[…] %s […]' % u' '.join(bits)


def pingable(handler):
    """
    Decorate a view function with this function to automatically set the
    `X-Pingback` header if the status code is 200.
    """
    def decorator(f):
        f.pingback_handler = handler
        def proxy(*args, **kwargs):
            response = f(*args, **kwargs)
            if response.status_code == 200:
                response['X-Pingback'] = href('portal', __service__='xmlrpc')
            return response
        return patch_wrapper(proxy, f)
    return decorator
