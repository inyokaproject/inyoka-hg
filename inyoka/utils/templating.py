# -*- coding: utf-8 -*-
"""
    inyoka.utils.templating
    ~~~~~~~~~~~~~~~~~~~~~~~

    This module contains functions for template-related things.

    :copyright: Copyright 2007 by Armin Ronacher, Benjamin Wiegand.
    :license: GNU GPL.
"""
import os
import simplejson
from jinja2 import Environment, FileSystemLoader
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


class InyokaEnvironment(Environment):
    """
    Beefed up version of the jinja environment but without security features
    to improve the performance of the lookups.
    """

    def __init__(self):
        loader = FileSystemLoader(os.path.join(os.path.dirname(__file__),
                                               os.pardir, 'templates'))
        Environment.__init__(self, loader=loader,
                             extensions=['jinja2.ext.TransExtension'],
                             auto_reload=settings.DEBUG,
                             cache_size=-1)
        self.globals.update(
            INYOKA_REVISION=INYOKA_REVISION,
            SETTINGS=settings,
            REQUEST=current_request,
            href=href
        )
        self.filters.update(
            timedeltaformat=
                lambda value, use_since=False:
                    format_timedelta(value, use_since=use_since),
            utctimedeltaformat=
                lambda value, use_since=False:
                    format_timedelta(value, use_since=use_since,
                                     enforce_utc=True),
            datetimeformat=
                lambda value:
                    format_datetime(value),
            utcdatetimeformat=
                lambda value:
                    format_datetime(value, enforce_utc=True),
            dateformat=
                lambda value, prefix=False:
                    natural_date(value, prefix),
            utcdateformat=
                lambda value, prefix=False:
                    natural_date(value, prefix, enforce_utc=True),
            timeformat=
                lambda value:
                    format_time(value),
            utctimeformat=
                lambda value:
                    format_time(value, enforce_utc=True),
            specificdatetimeformat=
                lambda value, alt=False:
                    format_specific_datetime(value, alt),
            utcspecificdatetimeformat=
                lambda value, alt=False:
                    format_specific_datetime(value, alt,
                                             enforce_utc=True),
            hnumber=
                lambda value, genus=None:
                    human_number(value, genus),
            url=
                lambda value, action=None:
                    url_for(value, action=action),
            jsonencode=simplejson.dumps
        )


# setup the template environment
jinja_env = InyokaEnvironment()


# circular imports
from inyoka.forum.acl import check_privilege
from inyoka.portal.models import PrivateMessageEntry
from inyoka.forum.models import Topic
from inyoka.ikhaya.models import Suggestion
from inyoka.utils.storage import storage
# set a new helper function for the templates
jinja_env.globals['check_privilege'] = check_privilege
