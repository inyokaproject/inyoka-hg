# -*- coding: utf-8 -*-
"""
    inyoka.utils.debug
    ~~~~~~~~~~~~~~~~~~

    This module is a fork of the `zine.utils.debug` module for use in inyoka.

    :copyright: 2009-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
import sys
from datetime import datetime
from textwrap import wrap
from werkzeug import escape, html
from django.db import connection
from django.db.backends import util
from django.utils import simplejson
from django.utils.encoding import force_unicode


_body_end_re = re.compile(r'</\s*(body|html)(?i)')
_comma_re = re.compile(r',(?=\S)')


TEMPLATE = u'''
<li><div class="topic{% if odd %} odd{% endif %}"><em>{{ topic }}</em> |
        <strong>took {{ "%.3f"|format(duration) }} ms</strong>
    </div>
    <div class="extra">
        <pre>{{ query }}</pre><pre>{{ data }}</pre>
        <div class="explain">
        {% if explain_result %}
        <strong>EXPLAIN Information</strong>
        <table>
            <tr><th>id</th><th>select_type</th><th>table</th><th>type</th><th>possible_key</th>
                <th>key</th><th>key_len</th><th>ref</th><th>rows</th><th>Extra</th></tr>
            {% for t in explain_result %}
            <tr><td>{{ t[0] }}</td><td>{{ t[1] }}</td><td>{{ t[2] }}</td><td>{{ t[3] }}</td>
                <td>{{ t[4] }}</td><td>{{ t[5] }}</td><td>{{ t[6] }}</td><td>{{ t[7] }}</td>
                <td>{{ t[8] }}</td><td>{{ t[9] }}</td></tr>
            {% endfor %}
        </table>
        {% endif %}
        </div>
    </div>
</li>'''


def debug_repr(obj):
    """
    A function that does a debug repr for an object.  This is used by all the
    `nodes`, `macros` and `parsers` so that we get a debuggable ast.
    """
    return '%s.%s(%s)' % (
        obj.__class__.__module__.rsplit('.', 1)[-1],
        obj.__class__.__name__,
        ', '.join('%s=%r' % (key, value)
        for key, value in sorted(getattr(obj, '__dict__', {}).items())
        if not key.startswith('_'))
    )


def find_calling_context(skip=2, module='inyoka'):
    """Finds the calling context."""
    frame = sys._getframe(skip)
    results = []
    while frame.f_back is not None:
        name = frame.f_globals.get('__name__')
        if name and (name == module or name.startswith(module + '.')):
            funcname = frame.f_code.co_name
            if 'self' in frame.f_locals:
                funcname = '%s.%s of %s' % (
                    frame.f_locals['self'].__class__.__name__,
                    funcname,
                    hex(id(frame.f_locals['self']))
                )
            elif 'template_name' in frame.f_locals:
                funcname = 'in template %s' % frame.f_locals['template_name']

            results.append('%s:%s (%s)' % (
                frame.f_code.co_filename,
                frame.f_lineno,
                funcname
            ))
        frame = frame.f_back
    if results:
        return results
    return ['<unknown>']


def render_query_table(request):
    """Renders a nice table of all queries in the page."""
    from inyoka.utils.templating import render_string

    queries = request.queries
    total = 0

    qresult = []
    _odd = False
    for statement, parameters, start, end, calling_context, explain in queries:
        total += (end - start)
        # find the proper calling context
        for frame in calling_context:
            if 'views' in frame:
                break
            elif 'template' in frame.lower():
                break

        qresult.append(render_string(TEMPLATE, {
            'topic': '%s %s' % (escape(frame), 'from SA'),
            'duration': (end - start) * 1000.0,
            'query': statement,
            'data': u'Parameters: %r' % (parameters,),
            'explain_result': explain,
            'odd': _odd,
        }))
        _odd = not _odd

    # render django queries into the debug toolbar
    django_queries = connection.queries[:]
    for query in django_queries:
        sql = u'\n'.join(wrap(u'\n'.join(x.rstrip() for x in query['raw_sql'].split('\n')), 120))

        explain_result = ""
        if sql.lower().strip().startswith('select'):
            cursor = connection.cursor()
            cursor.execute('EXPLAIN %s' % (sql,), query['params'])
            explain_result = cursor.fetchall()

        # find the proper calling context
        for frame in query['calling_context']:
            if 'views' in frame:
                break
            elif 'template' in frame.lower():
                break

        qresult.append(render_string(TEMPLATE, {
            'duration': query['time'],
            'query': sql,
            'explain_result': False,
            'data': u'Parameters: %s' % (query['params'],),
            'topic': '%s %s' % (escape(frame), 'from Django'),
            'odd': _odd,
            'explain_result': explain_result,
        }))
        _odd = not _odd
        total += float(query['time'] / 1000.0)

    # add cache queries
    if hasattr(request, 'cache_queries'):
        for query in request.cache_queries:
            qresult.append(render_string(TEMPLATE, {
                'topic': escape(u'%s from Cache' % query[0][0]),
                'query': escape(query[1]),
                'data': escape(query[2]),
                'duration': 0,
                'odd': _odd
            }))
            _odd = not _odd

    result = [u'<div id="database_debug_table">']
    stat = (u'<strong>(%d queries in %.2f ms + %d cache requests)</strong>'
            % (len(queries) + len(django_queries), total * 1000.0,
              len(request.cache_queries)))
    result.append(stat)
    result.append(u'<div id="database_debug_table_inner"><ul>')
    result.extend(qresult)
    result.append(u'<li>%s</li></ul></div></div>' % stat)

    result.append(html.script("""
        $(document).ready(function() {
            function toggleLog() {
                $('#database_debug_table_inner').toggle();
            }
            $('<a href="#database_debug_table">Show/Hide Log</a>').click(toggleLog)
                .prependTo($('#database_debug_table'));
            toggleLog();

            $('div.topic').click(function() {
                $(this).nextUntil('div.topic').toggle();
            });
            $('div.extra').hide();
        });
        """, type='text/javascript'))

    return u'\n'.join(result)


def inject_query_info(request, response):
    """Injects the collected queries into the response."""
    if not request.queries and not connection.queries:
        return
    debug_info = render_query_table(request).encode('utf-8')

    body = response.content
    match = _body_end_re.search(body)
    if match is not None:
        pos = match.start()
        response.content = body[:pos] + debug_info + body[pos:]
    else:
        response.content = body + '<hr>' + debug_info
    if 'content-length' in response:
        response['content-length'] = len(response.content)


def ms_from_timedelta(td):
    """
    Given a timedelta object, returns a float representing milliseconds
    """
    return (td.seconds * 1000) + (td.microseconds / 1000.0)


class DatabaseStatTracker(util.CursorDebugWrapper):
    """
        Replacement for CursorDebugWrapper which stores additional information
        in `connection.queries`.
    """
    def execute(self, sql, params=()):
        start = datetime.now()
        try:
            return self.cursor.execute(sql, params)
        finally:
            stop = datetime.now()
            duration = ms_from_timedelta(stop - start)
            # We keep `sql` to maintain backwards compatibility
            self.db.queries.append({
                'sql': self.db.ops.last_executed_query(self.cursor, sql, params),
                'time': duration,
                'raw_sql': sql,
                'params': params,
                'calling_context': find_calling_context()
            })


util.CursorDebugWrapper = DatabaseStatTracker
