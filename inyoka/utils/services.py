# -*- coding: utf-8 -*-
"""
    inyoka.utils.services
    ~~~~~~~~~~~~~~~~~~~~~

    This module implements a simple dispatcher for services.  Applications
    can still write their own but for 99% of the time this should work.


    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from inyoka.utils.http import HttpResponse


class SimpleDispatcher(object):
    """
    A very basic dispatcher.
    """

    def __init__(self, **methods):
        self.methods = methods

    def register(self, name=None):
        def decorator(f):
            name = name or f.__name__
            self.methods[name] = f
        return decorator

    def __call__(self, request, name):
        if name not in self.methods:
            return HttpResponse('Service not found.', status=404)
        try:
            return self.methods[name](request)
        except:
            return HttpResponse('Exception occured while running service', status=500)
