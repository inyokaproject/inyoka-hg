# -*- coding: utf-8 -*-
"""
    inyoka.utils.sessions
    ~~~~~~~~~~~~~~~~~~~~~

    Session related utility functions.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
import time
from datetime import datetime, timedelta
from inyoka.portal.models import SessionInfo
from inyoka.utils.urls import url_for
from inyoka.utils.storage import storage


SESSION_DELTA = 300


def set_session_info(request, action, category=None):
    """Set the session info."""
    if request.user.is_authenticated():
        #XXX: re-type the user in moderator, superuser and so on...
        user_type = 'user'
        subject = (request.user.username, user_type, url_for(request.user))
    else:
        # TODO: check user agent for bots and add extra entries for those.
        subject = (None, 'anonymous', None)

    try:
        info = SessionInfo.objects.get(key=request.session.session_key)
    except SessionInfo.DoesNotExist:
        info = SessionInfo(key=request.session.session_key)
    info.subject_text, info.subject_type, info.subject_link = subject
    info.action = action
    info.action_link = request.build_absolute_uri()
    info.category = category
    info.last_change = datetime.now()
    info.save()
    check_for_user_record()


def check_for_user_record():
    """Checks whether the current session count is a new record"""
    delta = datetime.now() - timedelta(seconds=SESSION_DELTA)
    record = int(storage.get('session_record', 0))
    session_count = SessionInfo.objects.filter(last_change__gt=delta).count()
    if session_count > record:
        storage['session_record'] = session_count
        storage['session_record_time'] = int(time.time())


def get_user_record():
    """
    Get a tuple for the user record in the format ``(number, timestamp)``
    where number is an integer with the number of online users and
    timestamp a datetime object.
    """
    record = int(storage.get('session_record', 0))
    timestamp = storage.get('session_record_time')
    if timestamp is None:
        timestamp = datetime.now()
    else:
        timestamp = datetime.fromtimestamp(int(timestamp))
    return record, timestamp


def get_sessions(order_by='-last_change'):
    """Get a simple list of active sessions for the portal index."""
    delta = datetime.now() - timedelta(seconds=SESSION_DELTA)
    sessions = []
    for item in SessionInfo.objects.filter(last_change__gt=delta) \
                                   .order_by(order_by):
        sessions.append({
            'anonymous':    item.subject_text is None,
            'text':         item.subject_text,
            'type':         item.subject_type,
            'link':         item.subject_link,
            'action':       item.action,
            'action_link':  item.action_link,
            'last_change':  item.last_change,
            'category':     item.category,
        })

    anonymous = sum(x['anonymous'] for x in sessions)
    return {
        'anonymous':            anonymous,
        'registered':           len(sessions) - anonymous,
        'all':                  len(sessions),
        'sessions':             sessions,
        'registered_sessions':  [s for s in sessions if not s['anonymous']]
    }


def make_permanent(request):
    """Make this session a permanent one."""
    request.session['is_permanent_session'] = True


def close_with_browser(request):
    """Close the session with the end of the browser session."""
    request.session['is_permanent_session'] = False
