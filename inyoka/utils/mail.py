# -*- coding: utf-8 -*-
"""
    inyoka.utils.mail
    ~~~~~~~~~~~~~~~~~

    This module provides various e-mail related functionality.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import re, os
from email.mime.text import MIMEText
from email.header import Header
from subprocess import Popen, PIPE
from dns.resolver import query as dns_query
from dns.exception import DNSException
#from django.core.mail import send_mail
from inyoka.utils.storage import storage


_mail_re = re.compile(r'''(?xi)
    (?:[a-z0-9!#$%&'*+/=?^_`{|}~-]+
        (?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*|
        "(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|
          \\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@
''')

def send_mail(subject, message_, from_, to):
    assert len(to) == 1

    message = u'From: %s\nTo: %s' % (from_ , to[0])
    # Ignore für den Fall, dass wir hier blöde emailadressen bekommen…
    # TODO: non ascii adressen erlauben
    message = message.encode('ascii', 'ignore')
    message += '\nSubject: ' + Header(subject, 'utf-8', header_name='Subject').encode() + '\n'
    message += MIMEText(message_.encode('utf-8'), _charset='utf-8').as_string()

    proc = Popen('nullmailer-inject', stdin=PIPE)
    proc.stdin.write(message)
    proc.stdin.close()
    # replace with os.wait() in a outer level to not wait to much?!
    proc.wait()


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


def is_blocked_host(email_or_host):
    """
    This function checks the email or host against a blacklist of hosts that
    is configurable in the admin panel.
    """
    host = email_or_host.rsplit('@', 1)[-1]
    return host in storage['blocked_hosts'].split('\n')
