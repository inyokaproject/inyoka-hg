# -*- coding: utf-8 -*-
"""
    inyoka.utils.services
    ~~~~~~~~~~~~~~~~~~~~~

    This module implements a simple dispatcher for services. Applications
    can still write their own but for 99% of the time this should work.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""


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
        if name in self.methods:
            return self.methods[name](request)
