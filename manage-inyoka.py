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
from werkzeug import script
from werkzeug.debug import DebuggedApplication
from werkzeug.contrib import profiler


def make_app():
    import inyoka.utils.http
    from inyoka.conf import settings
    from inyoka.application import application, StaticDomainHandler
    app = application
    app = StaticDomainHandler(app)
    if settings.DEBUG:
        app = DebuggedApplication(app, evalex=settings.ENABLE_DEBUGGER)
    return app


action_runserver = script.make_runserver(make_app, '', 8080,
                                         use_reloader=True)
action_shell = script.make_shell(lambda: {})
action_profiled = profiler.make_action(make_app, '', 8080)


def action_migrate():
    """Migrate to the latest revision."""
    from inyoka.utils.migrations import Migrations
    from inyoka.migrations import MIGRATIONS
    migrations = Migrations(MIGRATIONS)
    migrations.upgrade()


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
