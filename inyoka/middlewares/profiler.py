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
from inyoka.conf import settings
from inyoka.utils.http import HttpResponse
from inyoka.utils.html import escape
from collections import defaultdict
import time, socket
import gc


MEMORY_TEMPLATE = """<html>
<body>
<h1>Objects</h1>
<table>
%s
</table>
<h1>Garbage</h1>
<table>
%s
</table>
</body>
</html>"""
MEMORY_DATA_TEMPLATE = """<tr><td>%s</td><td>%s</td></tr>"""

class MemoryProfilerMiddleware(object):
    """
    This Middleware logs memory usage.
    """

    def process_request(self, request):
        if settings.DEBUG_LEAK and 'memory' in request.GET:
            data = defaultdict(int)
            for obj in gc.get_objects():
                data[type(obj)] += 1
            data = [(key, data[key]) for key in data if data[key] >= 100]
            data.sort(cmp=lambda x,y: cmp(x[1], y[1]), reverse=True)
            objdata = ''
            for obj, count in data:
                objdata += MEMORY_DATA_TEMPLATE % (escape(str(obj)), count)
            #Garbage
            data = defaultdict(int)
            for obj in gc.garbage:
                data[type(obj)] += 1
            data = [(key, data[key]) for key in data if data[key]]
            data.sort(cmp=lambda x,y: cmp(x[1], y[1]), reverse=True)
            garbagedata = ''
            for obj, count in data:
                garbagedata += MEMORY_DATA_TEMPLATE % (escape(str(obj)), count)
            return HttpResponse(MEMORY_TEMPLATE % (objdata, garbagedata))
        return
