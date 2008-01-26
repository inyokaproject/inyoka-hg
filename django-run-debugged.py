#!/usr/bin/env python
from werkzeug import run_simple, DebuggedApplication
from django.views import debug
from django.core.handlers.wsgi import WSGIHandler

def null_technical_500_response(request, exc_type, exc_value, tb):
    raise exc_type, exc_value, tb
debug.technical_500_response = null_technical_500_response

if __name__ == '__main__':
    run_simple('localhost', 8080, DebuggedApplication(WSGIHandler(), True))
