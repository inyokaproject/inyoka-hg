# -*- coding: utf-8 -*-
"""
    inyoka.utils.sessions
    ~~~~~~~~~~~~~~~~~~~~~

    Session related utility functions.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from time import time
from datetime import datetime, timedelta
from django.db import transaction
from django.newforms import ValidationError
from inyoka.portal.models import SessionInfo
from inyoka.utils.urls import url_for
from inyoka.utils.storage import storage
from inyoka.utils.http import DirectResponse, HttpResponseRedirect
from inyoka.utils.local import current_request


SESSION_DELTA = 300


@transaction.commit_on_success
def set_session_info(request, action, category=None):
    """Set the session info."""
    # if the session is new we don't add an entry.  It could be that
    # the user has no cookie support and that would fill our session
    # table with dozens of entries
    if request.session.new:
        return

    if request.user.is_authenticated:
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
    info.last_change = datetime.utcnow()

    # if there is an exception ignore it
    try:
        info.save()
    except:
        pass


class SurgeProtectionMixin(object):
    """
    Mixin for forms to override the `clean()` method to perform an additional
    surge protection.  Give this method a higher MRO than the form baseclass!
    """

    source_protection_timeout = 15
    source_protection_message = '''
        Du kannst Daten nicht so schnell hintereinander absenden.  Bitte
        warte noch einige Zeit bis du das Forumlar erneut absendest.
    '''
    source_protection_identifier = None

    def clean(self):
        identifier = self.source_protection_identifier or \
                     self.__class__.__module__.split('.')[1]
        storage = current_request.session.setdefault('sp', {})
        if storage.get(identifier, 0) >= time():
            raise ValidationError(self.source_protection_message)
        storage[identifier] = time() + self.source_protection_timeout
        return super(SurgeProtectionMixin, self).clean()


def get_user_record():
    """
    Get a tuple for the user record in the format ``(number, timestamp)``
    where number is an integer with the number of online users and
    timestamp a datetime object.
    """
    record = int(storage.get('session_record', 1))
    timestamp = storage.get('session_record_time')
    if timestamp is None:
        timestamp = datetime.utcnow()
    else:
        timestamp = datetime.fromtimestamp(int(timestamp))
    return record, timestamp


def get_sessions(order_by='-last_change'):
    """Get a simple list of active sessions for the portal index."""
    delta = datetime.utcnow() - timedelta(seconds=SESSION_DELTA)
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
    request.session['_perm'] = True


def close_with_browser(request):
    """Close the session with the end of the browser session."""
    request.session.pop('_perm', None)


def test_session_cookie(request):
    """
    Test if the session cookie works.  This is used in login and register
    to inform the user about an inproperly configured browser.  If the
    cookie doesn't work a link is returned to retry the configuration.
    """
    if request.session.new:
        arguments = request.GET.copy()
        if '_cookie_set' not in request.GET:
            arguments['_cookie_set'] = 'yes'
            this_url = 'http://%s%s%s' % (
                request.get_host(),
                request.path,
                arguments and '?' + arguments.urlencode() or ''
            )
            raise DirectResponse(HttpResponseRedirect(this_url))
        arguments.pop('_cookie_set', None)
        retry_link = 'http://%s%s%s' % (
            request.get_host(),
            request.path,
            arguments and '?' + arguments.urlencode() or ''
        )
    else:
        retry_link = None
    return retry_link
