# -*- coding: utf-8 -*-
"""
    inyoka.utils.database
    ~~~~~~~~~~~~~~~~~~~~~

    This module provides an SQLAlchemy metadata and engine.

    This module must never import application code so that migrations
    can work properly for bootstrapping and upgrading.

    The default session shutdown happens in the application handler in
    `inyoka.application`.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import scoped_session, create_session
from sqlalchemy.pool import NullPool
from inyoka.conf import settings

engine = create_engine('mysql://%s:%s@%s/%s?charset=utf8&use_unicode=0' % (
    settings.DATABASE_USER, settings.DATABASE_PASSWORD,
    settings.DATABASE_HOST, settings.DATABASE_NAME
), pool_recycle=25, convert_unicode=True, echo=settings.DATABASE_DEBUG,
   poolclass=NullPool)
metadata = MetaData(bind=engine)

session = scoped_session(lambda: create_session(engine,
    autoflush=True, transactional=True))


if settings.DEBUG:
    import logging
    engine_logger = logging.getLogger('sqlalchemy.engine')
    engine_logger.setLevel(logging.INFO)
    engine_logger.addHandler(logging.FileHandler('db.log'))


def select_blocks(query, pk, block_size=1000, start_with=0, max_fails=10):
    """Execute a query blockwise to prevent lack of ram"""
    range = (start_with, start_with + block_size)
    failed = 0
    while failed < max_fails:
        result = query.where(pk.between(*range)).execute()
        i = 0
        for i, row in enumerate(result):
            yield row
        if i == 0:
            failed += 1
        else:
            failed = 0
        range = range[1] + 1, range[1] + block_size
