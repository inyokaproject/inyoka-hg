# -*- coding: utf-8 -*-
"""
    inyoka.utils.legacyurls
    ~~~~~~~~~~~~~~~~~~~~~~~

    Support module for legacy url handling.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import re
from django.http import HttpResponsePermanentRedirect


def test_legacy_url(request, test_func):
    """
    This function currently does nothing but invoking the test function
    and if that one returns a url it returns a redirect response.  We
    could use this to add additional logging here.
    """
    old_url = test_func(request.path, request.GET)
    if old_url is not None:
        return HttpResponsePermanentRedirect(old_url)


def make_tester(f):
    return lambda request: test_legacy_url(request, f)


class LegacyDispatcher(object):
    """Helper class for legacy URLs."""

    def __init__(self):
        self.regexes = []

    def __call__(self, path, args):
        for regex, handler in self.regexes:
            match = regex.search(path)
            if match is not None:
                rv = handler(args, match, *match.groups())
                if rv is not None:
                    return rv

    def url(self, rule):
        def proxy(f):
            self.regexes.append((re.compile(rule), f))
            return f
        return proxy

    def tester(self, request):
        return test_legacy_url(request, self)
