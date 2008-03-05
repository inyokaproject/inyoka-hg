# -*- coding: utf-8 -*-
"""
    inyoka.utils.notification
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: Copyright 2007 by Benjamin Wiegand.
    :license: GNU GPL.
"""
from django.core.mail import send_mail
from inyoka.conf import settings
from inyoka.utils.jabber import send as send_jabber


def send_notification(user, subject, message):
    """
    This sends a message to the user using the person's favourite method(s)
    he has specified in the user control panel.
    """
    methods = user.settings.get('notify', ['mail'])
    if 'jabber' in methods and user.jabber:
        send_jabber(user.jabber, message, xhtml=False)
    if 'mail' in methods:
        send_mail(subject, message, settings.INYOKA_SYSTEM_USER_EMAIL,
                  [user.email])
