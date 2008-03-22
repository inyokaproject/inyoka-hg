# -*- coding: utf-8 -*-
"""
    inyoka.utils.database
    ~~~~~~~~~~~~~~~~~~~~~

    This module provides an SQLAlchemy metadata and engine.

    This module must never import application code so that migrations
    can work properly for bootstrapping and upgrading.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from django.dispatch import dispatcher
from django.core.signals import request_finished
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import scoped_session, create_session
from inyoka.conf import settings

engine = create_engine('mysql://%s:%s@%s/%s?charset=utf8' % (
    settings.DATABASE_USER, settings.DATABASE_PASSWORD,
    settings.DATABASE_HOST, settings.DATABASE_NAME
), pool_recycle=300, convert_unicode=False, echo=settings.DEBUG)
metadata = MetaData(bind=engine)

session = scoped_session(lambda: create_session(engine, transactional=True))
dispatcher.connect(session.remove, request_finished)
