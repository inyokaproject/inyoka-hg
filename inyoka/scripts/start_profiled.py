#!/usr/bin/env python
#-*- coding: utf-8 -*-
"""
    inyoka.scripts.start_profiled
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Start a django server with a profiler.

    :copyright: 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from django.core.handlers.wsgi import WSGIHandler
from django.core.servers.basehttp import run
from inyoka.middlewares._profiler import ProfilerMiddleware


app = ProfilerMiddleware(WSGIHandler())


if __name__ == '__main__':
    run('0.0.0.0', 8080, app)
