#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.cleanup_sessions
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Clean up unused sessions and session infos.

    :copyright: 2007 by Arimin Ronacher.
    :license: GNU GPL.
"""
from datetime import datetime, timedelta
from inyoka.portal.models import SessionInfo
from inyoka.utils.sessions import SESSION_DELTA
#from django.contrib.sessions.models import Session


def main():
    #Session.objects.filter(expire_date__lt=datetime.utcnow()).delete()
    SessionInfo.objects.filter(last_change__lt=datetime.utcnow() -
                               timedelta(seconds=SESSION_DELTA)).delete()


if __name__ == '__main__':
    main()
