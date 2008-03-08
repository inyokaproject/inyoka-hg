# -*- coding: utf-8 -*-
"""
    inyoka.ikhaya.database
    ~~~~~~~~~~~~~~~~~~~~~~

    Mappers for SqlAlchemy to query ikhaya more efficiently. This
    module is quite ugly and a bit redundant, but it bypasses some
    django limitations and we are going to migrate to SA anyway.

    :copyright: 2008 by Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
from sqlalchemy import Table, Column, String, Text, Integer, \
    ForeignKey, DateTime, UniqueConstraint, Boolean, create_engine, \
    MetaData, select
from sqlalchemy.orm import relation, backref, scoped_session, create_session
from inyoka.conf import settings
from inyoka.ikhaya.models import SAArticle, SACategory, SAComment, SAUser


metadata = MetaData()
engine = create_engine('%s://%s:%s@%s/%s' % (
    settings.DATABASE_ENGINE, settings.DATABASE_USER,
    settings.DATABASE_PASSWORD, settings.DATABASE_HOST, settings.DATABASE_NAME),
    pool_recycle=300, convert_unicode=True)
metadata.bind = engine

session = scoped_session(lambda: create_session(engine,
    transactional=True))
from django.dispatch import dispatcher
from django.core.signals import request_finished
dispatcher.connect(session.remove, request_finished)

article_table = Table('ikhaya_article', metadata, autoload=True)
category_table = Table('ikhaya_category', metadata, autoload=True)
comment_table = Table('ikhaya_comment', metadata, autoload=True)
user_table = Table('portal_user', metadata, autoload=True)


# set up the mappers for sqlalchemy
session.mapper(SACategory, category_table)
session.mapper(SAUser, user_table)
session.mapper(SAComment, comment_table, properties={
    'author': relation(SAUser,
        primaryjoin=comment_table.c.author_id==user_table.c.id,
        foreign_keys=[comment_table.c.author_id]),
})
session.mapper(SAArticle, article_table, properties={
    'category': relation(SACategory,
        primaryjoin=article_table.c.category_id==category_table.c.id,
        foreign_keys=[article_table.c.category_id]),
    'author': relation(SAUser,
        primaryjoin=article_table.c.author_id==user_table.c.id,
        foreign_keys=[article_table.c.author_id]),
    'comments': relation(SAComment, backref=backref('article'))
})

