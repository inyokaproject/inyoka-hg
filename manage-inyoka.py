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


if __name__ == '__main__':
    script.run()
