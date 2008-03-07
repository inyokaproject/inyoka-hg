# -*- coding: utf-8 -*-
"""
    inyoka.forum.database
    ~~~~~~~~~~~~~~~~~~~~~

    Mappers for SqlAlchemy to query the forum more efficiently. This
    module is quite ugly and a bit redundant, but it bypasses some
    django limitations and we are going to migrate to SA anyway.

    :copyright: 2008 by Christoph Hack.
    :license: GNU GPL, see LICENSE for more details.
"""
from sqlalchemy import Table, Column, String, Text, Integer, \
    ForeignKey, DateTime, UniqueConstraint, Boolean, create_engine, \
    MetaData, select
from sqlalchemy.orm import relation, backref, scoped_session, create_session
from inyoka.conf import settings
from inyoka.portal.models import User
from inyoka.forum.models import Forum, Topic, Post, Attachment


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

forum_table = Table('forum_forum', metadata, autoload=True)
topic_table = Table('forum_topic', metadata, autoload=True)
post_table = Table('forum_post', metadata, autoload=True)
user_table = Table('portal_user', metadata, autoload=True)
attachment_table = Table('forum_attachment', metadata, autoload=True)


class SAUser(User):
    __metaclass__ = type
    pass
class SAForum(Forum):
    __metaclass__ = type
    pass
class SATopic(Topic):
    __metaclass__ = type
    pass
class SAPost(Post):
    __metaclass__ = type
    pass
class SAAtachment(Attachment):
    __metaclass__ = type
    pass

# set up the mappers for sqlalchemy
session.mapper(SAUser, user_table)
session.mapper(SAAtachment, attachment_table)
session.mapper(SAForum, forum_table, properties={
    'last_post': relation(SAPost,
        primaryjoin=forum_table.c.last_post_id==post_table.c.id,
        foreign_keys=[forum_table.c.last_post_id])
})
session.mapper(SATopic, topic_table, properties={
    'forum': relation(SAForum,
        primaryjoin=topic_table.c.forum_id==forum_table.c.id,
        foreign_keys=[topic_table.c.forum_id]),
    'author': relation(SAUser,
        primaryjoin=topic_table.c.author_id==user_table.c.id,
        foreign_keys=[topic_table.c.author_id]),
    'last_post': relation(SAPost,
        primaryjoin=topic_table.c.last_post_id==post_table.c.id,
        foreign_keys=[topic_table.c.last_post_id])
})
session.mapper(SAPost, post_table, properties={
    'author': relation(SAUser,
        primaryjoin=post_table.c.author_id==user_table.c.id,
        foreign_keys=[post_table.c.author_id]),
    'attachments': relation(SAAtachment, backref=backref('post')),
})
