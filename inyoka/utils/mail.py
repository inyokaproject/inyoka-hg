# -*- coding: utf-8 -*-
"""
    inyoka.utils.mail
    ~~~~~~~~~~~~~~~~~

    This module provides various e-mail related functionality.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import re
from email.mime.text import MIMEText
from email.header import Header
from subprocess import Popen, PIPE
from inyoka.utils.storage import storage
from inyoka.conf import settings
from inyoka.tasks import send_mail as send_mail_task

_mail_re = re.compile(r'''(?xi)
    (?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+
        (?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|
        "(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|
          \\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@
''')

def send_mail(subject, message_, from_, to):
    return send_mail_task.delay(subject, message_, from_, to)


def may_be_valid_mail(email):
    """
    Check if the mail may be valid.  This does not check the hostname part
    of the email, for that you still have to test with `may_accept_mails`.
    """
    return _mail_re.match(email) is not None


def is_blocked_host(email_or_host):
    """
    This function checks the email or host against a blacklist of hosts that
    is configurable in the admin panel.
    """
    host = email_or_host.rsplit('@', 1)[-1]
    return host in storage['blocked_hosts'].split()
