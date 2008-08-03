# -*- coding: utf-8 -*-
"""
    inyoka.utils.notification
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: Copyright 2007 by Benjamin Wiegand, Marian Sigler.
    :license: GNU GPL.
"""
from smtplib import SMTPRecipientsRefused
from inyoka.conf import settings
from inyoka.utils.mail import send_mail
from inyoka.utils.jabber import send as send_jabber
from inyoka.utils.templating import render_template


def send_notification(user, template_name=None, subject=None, args={}):
    """
    Send a message to the user using the person's favourite method(s)
    he has specified in the user control panel.
    """
    assert subject is not None
    #TODO: use xhtml jabber messages
    methods = user.settings.get('notify', ['mail'])
    if 'jabber' in methods and user.jabber:
        message = render_template('mails/%s.jabber.txt' % template_name, args)
        send_jabber(user.jabber, message, xhtml=False)
    if 'mail' in methods:
        message = render_template('mails/%s.txt' % template_name, args)
        #XXX: this should be handled somewhat better... but if an email
        #     is corrupted we get an exception so we quit it quite
        try:
            send_mail(settings.EMAIL_SUBJECT_PREFIX + subject, message,
                      settings.INYOKA_SYSTEM_USER_EMAIL, [user.email])
        except SMTPRecipientsRefused:
            pass
