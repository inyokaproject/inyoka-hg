# -*- coding: utf-8 -*-
"""
    inyoka.utils.templating
    ~~~~~~~~~~~~~~~~~~~~~~~

    This module contains functions for template-related things.

    :copyright: Copyright 2007 by Armin Ronacher, Benjamin Wiegand.
    :license: GNU GPL.
"""
import os
from jinja import Environment, FileSystemLoader, MemcachedFileSystemLoader
from inyoka import INYOKA_REVISION
from inyoka.conf import settings
from inyoka.utils.dates import format_timedelta, natural_date, \
     format_datetime, format_specific_datetime, format_time
from inyoka.utils.text import human_number
from inyoka.utils.urls import href, url_for
from inyoka.utils.flashing import get_flashed_messages
from inyoka.utils.cache import cache
from inyoka.utils.local import current_request
from werkzeug import UserAgent


# path to the dtd.  In debug mode we refer to the file system, otherwise
# URL.  We do that because the firefox validator extension is unable to
# load DTDs from URLs...  On first rendering the path is calculated because
# of circular imports "href()" could cause.
inyoka_dtd = None


def get_dtd():
    """
    This returns either our dtd or our dtd + xml comment.  Neither is stricly
    valid as XML documents with custom doctypes must be served as XML but
    currently as MSIE is pain in the ass we have to workaround that IE bug
    by removing the XML PI comment.
    """
    global inyoka_dtd
    if inyoka_dtd is None:
        if settings.DEBUG:
            dtd_path = os.path.realpath(
                os.path.join(os.path.dirname(__file__), '..',
                             'static', 'xhtml1-strict-uu.dtd'))
        else:
            dtd_path = href('static', 'xhtml1-strict-uu.dtd')
        inyoka_dtd = '<!DOCTYPE html SYSTEM "%s">' % (
            settings.DEBUG and os.path.realpath(
                os.path.join(os.path.dirname(__file__), '..',
                             'static', 'xhtml1-strict-uu.dtd'))
            or href('static', 'xhtml1-strict-uu.dtd')
        )
    try:
        ua = UserAgent(current_request.META['HTTP_USER_AGENT'])
        if ua.browser == 'msie':
            return inyoka_dtd
    except:
        pass
    return '<?xml version="1.0" encoding="utf-8"?>\n' + inyoka_dtd


def populate_context_defaults(context):
    """Fill in context defaults."""
    try:
        request = current_request._get_current_object()
    except RuntimeError:
        request = None
    if request and request.user.is_authenticated:
        key = 'portal/pm_count/%s' % request.user.id
        pms = cache.get(key)
        if pms is None:
            pms = PrivateMessageEntry.objects.filter(user__id=request.user.id,
                                                  read=False).count()
            cache.set(key, pms)
        if not request.user.is_manager:
            reported = suggestions = 0
        else:
            key = 'forum/reported_topic_count'
            reported = cache.get(key)
            if reported is None:
                reported = Topic.query.filter(Topic.c.reported != None).count()
                cache.set(key, reported)
            key = 'ikhaya/suggestion_count'
            suggestions = cache.get(key)
            if suggestions is None:
                suggestions = Suggestion.objects.all().count()
                cache.set(key, suggestions)
    else:
        reported = pms = suggestions = 0

    # we don't have to use cache here because storage does this for us
    global_message = storage['global_message']

    if request:
        context.update(
            XHTML_DTD=get_dtd(),
            REQUEST=request,
            CURRENT_URL=request.build_absolute_uri(),
            USER=request.user,
            MESSAGES=get_flashed_messages()
        )

    context.update(
        GLOBAL_MESSAGE=global_message,
        pm_count=pms,
        report_count=reported,
        suggestion_count=suggestions
    )


def render_template(template_name, context):
    """Render a template.  You might want to set `req` to `None`."""
    tmpl = jinja_env.get_template(template_name)
    populate_context_defaults(context)
    return tmpl.render(context)


def partial_renderable(template_name, macro_name=None):
    """Helper function for partial templates."""
    def decorate(f=lambda **kw: kw):
        def oncall(*args, **kwargs):
            return render_template(template_name, f(*args, **kwargs) or {})
        oncall.__name__ = name = macro_name or f.__name__
        oncall.__doc__ = f.__doc__
        oncall.__module__ = f.__module__
        jinja_env.globals['h'][name] = oncall
        return oncall
    return decorate


class InyokaEnvironment(Environment):
    """
    Beefed up version of the jinja environment but without security features
    to improve the performance of the lookups.
    """

    def __init__(self):
        use_memcache = settings.TEMPLATE_CACHING
        if use_memcache is None:
            use_memcache = not settings.DEBUG
        loader = None
        if settings.MEMCACHE_SERVERS:
            loader = MemcachedFileSystemLoader(os.path.join(
                os.path.dirname(__file__), os.pardir, 'templates'),
                memcache_host=settings.MEMCACHE_SERVERS,
                use_memcache=use_memcache)
        else:
            loader = FileSystemLoader(os.path.join(os.path.dirname(__file__),
                os.pardir, 'templates'),
                use_memcache=use_memcache, memcache_size=200)
        Environment.__init__(self, loader=loader)
        self.globals.update(
            INYOKA_REVISION=INYOKA_REVISION,
            SETTINGS=settings,
            href=href,
            h={}
        )
        self.filters.update(
            timedeltaformat=
                lambda use_since=False:
                    lambda env, context, value:
                        format_timedelta(value, use_since=use_since),
            utctimedeltaformat=
                lambda use_since=False:
                    lambda env, context, value:
                        format_timedelta(value, use_since=use_since,
                                         enforce_utc=True),
            datetimeformat=
                lambda:
                    lambda env, context, value:
                        format_datetime(value),
            utcdatetimeformat=
                lambda:
                    lambda env, context, value:
                        format_datetime(value, enforce_utc=True),
            dateformat=
                lambda prefix=False:
                    lambda env, context, value:
                        natural_date(value, prefix),
            utcdateformat=
                lambda prefix=False:
                    lambda env, context, value:
                        natural_date(value, prefix, enforce_utc=True),
            timeformat=
                lambda:
                    lambda env, context, value:
                        format_time(value),
            utctimeformat=
                lambda:
                    lambda env, context, value:
                        format_time(value, enforce_utc=True),
            specificdatetimeformat=
                lambda alt=False:
                    lambda env, context, value:
                        format_specific_datetime(value, alt),
            utcspecificdatetimeformat=
                lambda alt=False:
                    lambda env, context, value:
                        format_specific_datetime(value, alt,
                                                 enforce_utc=True),
            hnumber=
                lambda genus=None:
                    lambda env, context, value:
                        human_number(value, genus),
            url=
                lambda action=None:
                    lambda env, context, value:
                        url_for(value, action=action)
        )

    def finish_var(self, value, ctx, unicode=unicode):
        """disable fancy jinja finalization."""
        return unicode(value)

    def get_attribute(self, obj, name, getattr=getattr):
        """Faster attribute lookup without sanity cehcks."""
        try:
            return obj[name]
        except (TypeError, KeyError, IndexError, AttributeError):
            try:
                return getattr(obj, name)
            except (AttributeError, TypeError):
                # TypeError is needed because getattr(obj, integer) isn't
                # allowed
                pass
        return self.undefined_singleton

    def call_function_simple(self, f, context, getattr=getattr):
        """No sanity checks"""
        if getattr(f, 'jinja_context_callable', False):
            return f(self, context)
        return f()

    def call_function(self, f, context, args, kwargs, dyn_args, dyn_kwargs):
        """No sanity checks."""
        if dyn_args is not None:
            args += tuple(dyn_args)
        if dyn_kwargs is not None:
            kwargs.update(dyn_kwargs)
        if getattr(f, 'jinja_context_callable', False):
            args = (self, context) + args
        return f(*args, **kwargs)


# setup the template environment
jinja_env = InyokaEnvironment()


# circular imports
from inyoka.portal.models import PrivateMessageEntry
from inyoka.forum.models import Topic
from inyoka.ikhaya.models import Suggestion
from inyoka.utils.storage import storage
from inyoka.forum.acl import check_privilege
# set a new helper function for the templates
jinja_env.globals['check_privilege'] = check_privilege
