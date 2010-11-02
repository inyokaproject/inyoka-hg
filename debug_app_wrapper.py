def make_app():
    import gc
    import inyoka.utils.http
    from inyoka.conf import settings
    from inyoka.application import application, StaticDomainHandler
    from werkzeug import DebuggedApplication
    app = application
    app = StaticDomainHandler(app)
    if settings.DEBUG:
        app = DebuggedApplication(app, evalex=settings.ENABLE_DEBUGGER)
    if settings.DEBUG_LEAK:
        gc.set_debug(gc.DEBUG_SAVEALL)
    return app

app = make_app()
