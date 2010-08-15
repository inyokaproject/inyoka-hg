#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.cleanup_sessions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Clean up unused sessions and session infos.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from datetime import datetime, timedelta
# fix import error for now
from inyoka import application
from inyoka.portal.models import SessionInfo
from inyoka.utils.sessions import SESSION_DELTA
#from django.contrib.sessions.models import Session


def main():
    #Session.objects.filter(expire_date__lt=datetime.utcnow()).delete()
    SessionInfo.objects.filter(last_change__lt=datetime.utcnow() -
                               timedelta(seconds=SESSION_DELTA)).delete()


if __name__ == '__main__':
    main()
