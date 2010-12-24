# -*- coding: utf-8 -*-
"""
    inyoka.utils.feeds
    ~~~~~~~~~~~~~~~~~~~

    Utils for creating an atom feed.  This module relies in :mod:`werkzeug.contrib.atom`.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from os.path import join
from werkzeug.contrib.atom import AtomFeed
from inyoka.utils.html import escape
from inyoka.utils.http import HttpResponse, PageNotFound, \
    HttpResponsePermanentRedirect
from inyoka.utils.cache import cache


AVAILABLE_FEED_COUNTS = (25,)

def atom_feed(cache_key=None, available_counts=AVAILABLE_FEED_COUNTS):
    def decorator(f):
        def func(*args, **kwargs):
            if kwargs.get('mode') not in ('full', 'short', 'title'):
                raise PageNotFound()

            kwargs['count'] = count = int(kwargs['count'])

            #: Legacy: We changed the available feeds to only 25 items because
            #:         of performance problems.  This exists to properly
            #:         redirect users feedreaders to the new views.
            if count in (10, 20, 30, 50, 75, 100) and count not in available_counts:
                base_uri = u'/'.join(args[0].path.split('/')[:-2])
                redirect_uri = join(base_uri, str(max(available_counts)))
                return HttpResponsePermanentRedirect(redirect_uri)

            if kwargs['count'] not in available_counts:
                raise PageNotFound()

            if cache_key is not None:
                key = cache_key % kwargs
                content = cache.get(key)
                if content is None:
                    rv = f(*args, **kwargs)
                    if not isinstance(rv, AtomFeed):
                        # ret is a HttpResponse object
                        return rv
                    content = rv.to_string()
                    cache.set(key, content, 600)

            content_type='application/atom+xml; charset=utf-8'
            response = HttpResponse(content, content_type=content_type)

            return response
        return func
    return decorator
