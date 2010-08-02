#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Inyoka Management Script
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Starts server and debugger.  This script may never globally import stuff
    from inyoka as the migrations have to load the SQLAlchemy database layout
    without invoking the autoloading mechanism of the tables.  Otherwise it
    will be impossible to use them.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from functools import partial
from werkzeug import script
from werkzeug.debug import DebuggedApplication
from werkzeug.contrib import profiler
import gc


def make_app():
    import inyoka.utils.http
    from inyoka.conf import settings
    from inyoka.application import application, StaticDomainHandler
    app = application
    app = StaticDomainHandler(app)
    if settings.DEBUG:
        app = DebuggedApplication(app, evalex=settings.ENABLE_DEBUGGER)
    if settings.DEBUG_LEAK:
        gc.set_debug(gc.DEBUG_SAVEALL)
    return app


action_shell = script.make_shell(lambda: {})
action_profiled = profiler.make_action(make_app, '', 8080)


def action_runserver(hostname='', port=8080, server='simple'):
    from inyoka.conf import settings

    parts = settings.BASE_DOMAIN_NAME.split(':')
    if not hostname:
        hostname = parts[0] or 'localhost'
    port = int(parts[1]) if len(parts) > 1 else port

    app = make_app()

    def _simple():
        from werkzeug.serving import run_simple
        run_simple(hostname, port, app, threaded=False,
            processes=1, use_reloader=True, use_debugger=False)

    def _eventlet():
        from eventlet import api, wsgi
        wsgi.server(api.tcp_listener((hostname, port)), app)

    def _cherrypy():
        from cherrypy.wsgiserver import CherryPyWSGIServer
        server = CherryPyWSGIServer((hostname, port), app,
            server_name=settings.BASE_DOMAIN_NAME,
            request_queue_size=500)
        server.start()

    def _tornado():
        from tornado import httpserver, ioloop, wsgi
        container = wsgi.WSGIContainer(app)
        http_server = httpserver.HTTPServer(container)
        http_server.listen(port, hostname)
        ioloop.IOLoop.instance().start()

    def _gevent():
        from gevent import monkey; monkey.patch_all()
        from gevent.wsgi import WSGIServer
        WSGIServer((hostname, port), app).serve_forever()

    def _meinheld():
        from meinheld import server
        server.listen((hostname, port))
        server.run(app)

    mapping = {
        'simple': _simple,
        'eventlet': _eventlet,
        'cherrypy': _cherrypy,
        'tornado': _tornado,
        'gevent': _gevent,
        'meinheld': _meinheld
    }

    # run actually the server
    mapping[server]()


def action_create_superuser(username='', email='', password=''):
    """
    Create a user with all privileges.  If you don't provide an argument
    the script will prompt you for it.
    """
    from getpass import getpass
    while not username:
        username = raw_input('username: ')
    while not email:
        email = raw_input('email: ')
    if not password:
        while not password:
            password = getpass('password: ')
            if password:
                if password == getpass('repeat: '):
                    break
                password = ''
    import inyoka.application
    from inyoka.portal.user import User, PERMISSION_NAMES
    from inyoka.forum.models import Forum, Privilege
    from inyoka.forum.acl import PRIVILEGES_DETAILS, join_flags
    from inyoka.utils.database import session
    user = User.objects.register_user(username, email, password, False)
    permissions = 0
    for perm in PERMISSION_NAMES.keys():
        permissions |= perm
    user._permissions = permissions
    user.save()
    bits = dict(PRIVILEGES_DETAILS).keys()
    bits = join_flags(*bits)
    for forum in Forum.query.all():
        privilege = Privilege(
            user=user,
            forum=forum,
            positive=bits,
            negative=0
        )
        session.save(privilege)
    session.commit()
    session.flush()
    print 'created superuser'


def action_runcp(hostname='0.0.0.0', port=8080):
    """Run the application in CherryPy."""
    from cherrypy.wsgiserver import CherryPyWSGIServer
    server = CherryPyWSGIServer((hostname, port), make_app())
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


def action_mysql():
    import sys
    from subprocess import Popen
    from inyoka.conf import settings
    cmd = ['mysql', settings.DATABASE_NAME]
    if settings.DATABASE_USER:
        cmd.extend(('-u', settings.DATABASE_USER))
    if settings.DATABASE_PASSWORD:
        cmd.append('-p%s' % settings.DATABASE_PASSWORD)
    if settings.DATABASE_HOST:
        cmd.extend(('-h', settings.DATABASE_HOST))
    p = Popen(cmd, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    return p.wait()


def action_dropdb():
    from django.db import connection
    from south.db import db

    tables = connection.introspection.table_names()
    db.start_transaction()
    for table in tables:
        db.delete_table(table)
    db.commit_transaction()


def _dowse():
    try:
        from dozer import Dozer
        app = Dozer(make_app())
    except ImportError:
        app = make_app()

    return app
action_dozer = script.make_runserver(_dowse, '', 8080, use_reloader=True)


if __name__ == '__main__':
    script.run()
