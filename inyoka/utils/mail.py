# -*- coding: utf-8 -*-
"""
    inyoka.utils.mail
    ~~~~~~~~~~~~~~~~~

    This module provides various e-mail related functionality.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import re
from dns.resolver import query as dns_query
from dns.exception import DNSException
from django.core.mail import send_mail


_mail_re = re.compile(r'''(?xi)
    (?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+
        (?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|
        "(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|
          \\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@
''')


def may_be_valid_mail(email):
    """
    Check if the mail may be valid.  This does not check the hostname part
    of the email, for that you still have to test with `may_accept_mails`.
    """
    return _mail_re.match(email) is not None


def may_accept_mails(email_or_host, timeout=2):
    """
    This function performs a DNS query on the host in the mail or the host
    provided to see if the server may accept mails.  We don't try to contact
    the SMTP server listening because most likely a server admin may flag
    this as suspicious behavior and blacklist us.
    """
    host = email_or_host.rsplit('@', 1)[-1]
    try:
        answer = list(dns_query(host, 'MX'))
        if not answer:
            raise DNSException()
    except DNSException:
        return False
    return bool(answer)
