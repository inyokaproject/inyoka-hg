# -*- coding: utf-8 -*-
"""
    Inyoka Management Script
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Starts server and debugger.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from inyoka.conf import settings
from inyoka.application import application, StaticDomainHandler
from werkzeug import script
from werkzeug.debug import DebuggedApplication
from werkzeug.contrib import profiler


def make_app():
    app = application
    app = StaticDomainHandler(app)
    if settings.DEBUG:
        app = DebuggedApplication(app, evalex=settings.ENABLE_DEBUGGER)
    return app


action_runserver = script.make_runserver(make_app, port=8080,
                                         use_reloader=True)
action_shell = script.make_shell(lambda: {})
action_profiled = profiler.make_action(make_app, port=8080)


if __name__ == '__main__':
    script.run()
