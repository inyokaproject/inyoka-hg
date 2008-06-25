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
from sqlalchemy import Table, Column, String, Text, Integer, \
        ForeignKey, DateTime, UniqueConstraint, Boolean, Index
from inyoka.utils.database import metadata, session


forum_table = Table('forum_forum', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(100), nullable=False),
    Column('slug', String(100), nullable=False, unique=True, index=True),
    Column('description', String(500), nullable=False, default=''),
    Column('parent_id', Integer, ForeignKey('forum_forum.id'),
           nullable=True, index=True),
    Column('position', Integer, nullable=False, default=0),
    Column('last_post_id', Integer, ForeignKey('forum_post.id',
            use_alter=True, name='forum_forum_lastpost_fk'), nullable=True),
    Column('post_count', Integer, default=0, nullable=False),
    Column('topic_count', Integer, default=0, nullable=False),
    Column('welcome_message_id', Integer, ForeignKey('forum_welcomemessage.id'),
           nullable=True),
    Column('newtopic_default_text', Text, nullable=False),
)

topic_table = Table('forum_topic', metadata,
    Column('id', Integer, primary_key=True),
    Column('forum_id', Integer, ForeignKey('forum_forum.id')),
    Column('title', String(100), nullable=False),
    Column('slug', String(50), nullable=False, index=True),
    Column('view_count', Integer, default=0, nullable=False),
    Column('post_count', Integer, default=0, nullable=False),
    Column('sticky', Boolean, default=False, nullable=False),
    Column('solved', Boolean, default=False, nullable=False),
    Column('locked', Boolean, default=False, nullable=False),
    Column('reported', Text(), nullable=True),
    Column('reporter_id', Integer, ForeignKey('portal_user.id'),
            nullable=True),
    Column('hidden', Boolean, default=False, nullable=False),
    Column('ubuntu_version', String(5), nullable=True),
    Column('ubuntu_distro', String(40), nullable=True),
    Column('author_id', Integer, ForeignKey('portal_user.id'),
            nullable=False),
    Column('first_post_id', Integer, ForeignKey('forum_post.id',
            use_alter=True, name='forum_topic_firstpost_fk'), nullable=True),
    Column('last_post_id', Integer, ForeignKey('forum_post.id',
            use_alter=True, name='forum_topic_lastpost_fk'), nullable=True),
    Column('has_poll', Boolean, default=False, nullable=False)
)

post_table = Table('forum_post', metadata,
    Column('id', Integer, primary_key=True),
    Column('position', Integer),
    Column('author_id', Integer, ForeignKey('portal_user.id'),
           nullable=False),
    Column('pub_date', DateTime, nullable=False, index=True),
    Column('topic_id', Integer, ForeignKey('forum_topic.id'), nullable=False),
    Column('hidden', Boolean, default=False, nullable=False),
    Column('text', Text(), nullable=False),
    Column('rendered_text', Text(), nullable=False),
)

post_revision_table = Table('forum_postrevision', metadata,
    Column('id', Integer, primary_key=True),
    Column('post_id', Integer, ForeignKey('forum_post.id'), nullable=False),
    Column('text', Text(), nullable=False),
    Column('store_date', DateTime, nullable=False),
)

poll_table = Table('forum_poll', metadata,
    Column('id', Integer, primary_key=True),
    Column('question', String(250), nullable=False),
    Column('topic_id', Integer, ForeignKey('forum_topic.id'), nullable=True,
          index=True),
    Column('start_time', DateTime, nullable=False),
    Column('end_time', DateTime, nullable=False),
    Column('multiple_votes', Boolean, default=False, nullable=False)
)

poll_option_table = Table('forum_polloption', metadata,
    Column('id', Integer, primary_key=True),
    Column('poll_id', Integer, ForeignKey('forum_poll.id'), nullable=False),
    Column('name', String(250), nullable=False),
    Column('votes', Integer, default=0, nullable=False)
)

poll_vote_table = Table('forum_voter', metadata,
    Column('id', Integer, primary_key=True),
    Column('voter_id', Integer, ForeignKey('portal_user.id'), nullable=False),
    Column('poll_id', Integer, ForeignKey('forum_poll.id'), nullable=False)
)

privilege_table = Table('forum_privilege', metadata,
    Column('id', Integer, primary_key=True),
    Column('group_id', Integer, nullable=True),
    Column('user_id', Integer, ForeignKey('portal_user.id'), nullable=True),
    Column('forum_id', Integer, ForeignKey('forum_forum.id'), nullable=False),
    Column('bits', Integer, nullable=True),
)

user_table = Table('portal_user', metadata, autoload=True)
user_group_table = Table('portal_user_groups', metadata, autoload=True)
group_table = Table('portal_group', metadata, autoload=True)
forum_welcomemessage_table = Table('forum_welcomemessage', metadata,
                                   autoload=True)
attachment_table = Table('forum_attachment', metadata,
    Column('id', Integer, primary_key=True),
    Column('file', String(100), unique=True, nullable=False),
    Column('name', String(255), nullable=False),
    Column('comment', Text(), nullable=True),
    Column('post_id', Integer, ForeignKey('forum_post.id'), nullable=True),
    Column('mimetype', String(100), nullable=True),
)

# initialize indexes
Index('viewtopic', post_table.c.topic_id, post_table.c.position)
Index('viewforum', topic_table.c.forum_id, topic_table.c.sticky,
      topic_table.c.last_post_id)


metadata.create_all()
