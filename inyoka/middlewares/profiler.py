#-*- coding: utf-8 -*-
"""
    inyoka.middlewares.profiler
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This middleware profiles our db queries, memory usage and other
    counters...

    :copyright: 2008 by Christopher Grebs.
    :license: GNU GPL.
"""
from datetime import datetime
from inyoka.utils.logger import memlogger
import time, socket



class MemoryProfilerMiddleware(object):
    """
    This Middleware logs memory usage.
    """

    def process_response(self, request, response):
        if request.subdomain and request.subdomain not in ('static', 'media') and \
            socket.gethostname() == 'jok':
            memlogger.log(request.build_absolute_uri(), request.method)
        return response
