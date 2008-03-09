# -*- coding: utf-8 -*-
"""
    inyoka.forum.database
    ~~~~~~~~~~~~~~~~~~~~~

    Mappers for SqlAlchemy to query the forum more efficiently. This
    module is quite ugly and a bit redundant, but it bypasses some
    django limitations and we are going to migrate to SA anyway.

    :copyright: 2008 by Christoph Hack, Christopher Grebs.
    :license: GNU GPL, see LICENSE for more details.
"""
from sqlalchemy import Table
from sqlalchemy.orm import relation, backref
from inyoka.utils.database import metadata, session
from inyoka.forum.models import SAForum, SATopic, SAPost, SAAttachment, SAUser


forum_table = Table('forum_forum', metadata, autoload=True)
topic_table = Table('forum_topic', metadata, autoload=True)
post_table = Table('forum_post', metadata, autoload=True)
user_table = Table('portal_user', metadata, autoload=True)
attachment_table = Table('forum_attachment', metadata, autoload=True)


# set up the mappers for sqlalchemy
session.mapper(SAUser, user_table)
session.mapper(SAAttachment, attachment_table)
session.mapper(SAForum, forum_table, properties={
    'last_post': relation(SAPost,
        primaryjoin=forum_table.c.last_post_id==post_table.c.id,
        foreign_keys=[forum_table.c.last_post_id]),
    'parent': relation(SAForum,
        foreign_keys=[forum_table.c.parent_id])
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
    'attachments': relation(SAAttachment, backref=backref('post')),
})
