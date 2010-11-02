# -*- coding: utf-8 -*-
"""
    inyoka.utils.xmlrpc
    ~~~~~~~~~~~~~~~~~~~

    This module implements a XMLRPC service.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import sys
from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
from inyoka.utils.http import HttpResponse


class XMLRPC(object, SimpleXMLRPCDispatcher):
    """
    A XMLRPC dispatcher that uses our request and response objects.  It
    also works around a problem with Python 2.4 / 2.5 compatibility and
    registers the introspection functions automatically.
    """

    def __init__(self, no_introspection=False):
        if sys.version_info[:2] < (2, 5):
            SimpleXMLRPCDispatcher.__init__(self)
        else:
            SimpleXMLRPCDispatcher.__init__(self, False, 'utf-8')
        if not no_introspection:
            self.register_introspection_functions()

    def handle_request(self, request):
        if request.method == 'POST':
            response = self._marshaled_dispatch(request.data)
            return HttpResponse(response, mimetype='application/xml')
        response = HttpResponse('\n'.join((
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">',
            '<title>XMLRPC Interface</title>',
            '<h1>XMLRPC Interface</h1>',
            '<p>This URL provides an XMLRPC interface.  You have to '
            'connect to it using an XMLRPC client.</p>'
        )))
        response['Allow'] = 'POST'
        response.status_code = 405
        return response

    def __call__(self, request):
        return self.handle_request(request)


xmlrpc = XMLRPC()


def register(name):
    """Register a function for the global xmlrpc server."""
    def proxy(f):
        xmlrpc.register_function(f, name)
        return f
    return proxy
