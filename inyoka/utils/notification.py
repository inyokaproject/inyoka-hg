# -*- coding: utf-8 -*-
"""
    inyoka.utils.notification
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from inyoka.conf import settings
from inyoka.utils.mail import send_mail
from inyoka.utils.jabber import send as send_jabber
from inyoka.utils.templating import render_template

def send_notification(user, template_name=None, subject=None, args=None):
    """
    Send a message to the user using the person's favourite method(s)
    he has specified in the user control panel.
    """
    assert subject is not None
    args = args or {}

    if user.is_deleted:
        return

    #TODO: use xhtml jabber messages
    methods = user.settings.get('notify', ['mail'])
    if 'jabber' in methods and user.jabber:
        message = render_template('mails/%s.jabber.txt' % template_name, args)
        send_jabber(user.jabber, message, xhtml=False)
    if 'mail' in methods:
        message = render_template('mails/%s.txt' % template_name, args)
        send_mail(settings.EMAIL_SUBJECT_PREFIX + subject, message,
                  settings.INYOKA_SYSTEM_USER_EMAIL, [user.email])


def notify_about_subscription(sub, template=None, subject=None, args=None):
    args = args or {}
    if not sub.can_read:
        # don't send subscriptions to user that don't have read
        # access to the resource
        return

    send_notification(sub.user, template, subject, args)
