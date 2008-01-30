# -*- coding: utf-8 -*-
"""
    inyoka.utils.templating
    ~~~~~~~~~~~~~~~~~~~~~~~

    This module contains functions for template-related things.

    :copyright: Copyright 2007 by Armin Ronacher, Benjamin Wiegand.
    :license: GNU GPL.
"""
import os
from jinja import Environment, FileSystemLoader
from django.conf import settings
from django.core.cache import cache
from inyoka.utils import format_timedelta, human_number, natural_date, \
                         format_datetime, format_specific_datetime, \
                         format_time, INYOKA_REVISION
from inyoka.utils.urls import href, url_for
from inyoka.utils.flashing import get_flashed_messages
from inyoka.middlewares.registry import r


# we could use the MemcachedFileSystemLoader too
jinja_env = Environment(loader=FileSystemLoader(
    os.path.join(os.path.dirname(__file__), os.pardir, 'templates'),
    use_memcache=not settings.DEBUG,
    memcache_size=100
))
jinja_env.globals.update(
    INYOKA_REVISION=INYOKA_REVISION,
    #XXX: just allow some vars?
    SETTINGS=settings,
    href=href,
    h={}
)
jinja_env.filters.update(
    timedeltaformat=
        lambda use_since=False:
            lambda env, context, value:
                format_timedelta(value, use_since=use_since),
    datetimeformat=
        lambda:
            lambda env, context, value:
                format_datetime(value),
    dateformat=
        lambda:
            lambda env, context, value:
                natural_date(value),
    timeformat=
        lambda:
            lambda env, context, value:
                format_time(value),
    specificdatetimeformat=
        lambda alt=False:
            lambda env, context, value:
                format_specific_datetime(value, alt),
    hnumber=
        lambda genus=None:
            lambda env, context, value:
                human_number(value, genus),
    url=
        lambda action=None:
            lambda env, context, value:
                url_for(value, action=action)
)


def populate_context_defaults(context):
    """Fill in context defaults."""
    request = r.request
    if request.user.is_authenticated:
        key = 'portal/pm_count/%s' % request.user.id
        pms = cache.get(key)
        if pms is None:
            pms = PrivateMessageEntry.objects.filter(user__id=request.user.id,
                                                  read=False).count()
            cache.set(key, pms)
        # XXX: permission check
        key = 'forum/reported_topic_count'
        reported = cache.get(key)
        if reported is None:
            reported = Topic.objects.filter(reported__isnull=False).count()
            cache.set(key, reported)
        key = 'ikhaya/suggestion_count'
        suggestions = cache.get(key)
        if suggestions is None:
            suggestions = Suggestion.objects.all().count()
            cache.set(key, suggestions)
    else:
        reported = pms = suggestions = 0

    context.update(
        REQUEST=request,
        CURRENT_URL=request.build_absolute_uri(),
        USER=request and request.user or None,
        MESSAGES=get_flashed_messages(),
        GLOBAL_MESSAGE=storage['global_message'],
        pm_count=pms,
        report_count=reported,
        suggestion_count=suggestions
    )


def render_template(template_name, context):
    """Render a template. You might want to set `req` to `None`."""
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


# circular imports
from inyoka.portal.models import PrivateMessageEntry
from inyoka.forum.models import Topic
from inyoka.ikhaya.models import Suggestion
from inyoka.utils.storage import storage
