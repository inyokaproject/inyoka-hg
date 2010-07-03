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
        ForeignKey, DateTime, Boolean, Index, PickleType
from inyoka.utils.database import metadata
from inyoka import conf


forum_table = Table('forum_forum', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(100), nullable=False),
    Column('slug', String(100), nullable=False, unique=True, index=True),
    Column('description', String(500), nullable=False, default=''),
    Column('parent_id', Integer, ForeignKey('forum_forum.id'),
           nullable=True, index=True),
    Column('position', Integer, nullable=False, default=0),
    Column('last_post_id', Integer, ForeignKey('forum_post.id',
            use_alter=True, name='forum_forum_lastpost_id'), nullable=True),
    Column('post_count', Integer, default=0, nullable=False),
    Column('topic_count', Integer, default=0, nullable=False),
    Column('welcome_message_id', Integer, ForeignKey('forum_welcomemessage.id'),
           nullable=True),
    Column('newtopic_default_text', Text, nullable=True),
    Column('user_count_posts', Boolean, default=True, nullable=False),
    Column('force_version', Boolean, default=False, nullable=False)
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
    Column('report_claimed_by_id', Integer, ForeignKey('portal_user.id')),
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
    Column('position', Integer, nullable=False, default=0),
    Column('author_id', Integer, ForeignKey('portal_user.id'),
           nullable=False),
    Column('pub_date', DateTime, nullable=False, index=True),
    Column('topic_id', Integer, ForeignKey('forum_topic.id'), nullable=False),
    Column('hidden', Boolean, default=False, nullable=False),
    Column('text', Text(), nullable=False),
    Column('rendered_text', Text(), nullable=True),
    Column('has_revision', Boolean, default=False, nullable=False),
    Column('is_plaintext', Boolean, default=False, nullable=False)
)

post_revision_table = Table('forum_postrevision', metadata,
    Column('id', Integer, primary_key=True),
    Column('post_id', Integer, ForeignKey('forum_post.id'), nullable=False),
    Column('text', Text(), nullable=False),
    Column('store_date', DateTime, nullable=False)
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
    Column('positive', Integer, nullable=True),
    Column('negative', Integer, nullable=True)
)

#XXX Please note that those portal_* tables should not be used too much
#    to stay in sync with Django.  If modify something here, modify it in
#    the appropriate portal model too!
#
#    If you have time take a look if everything's in sync!

user_table = Table('portal_user', metadata,
    Column('id', Integer, primary_key=True),
    Column('username', String(30), nullable=False, unique=True),
    Column('email', String(50), unique=True, nullable=False),
    Column('password', String(128), nullable=False),
    Column('status', Integer, nullable=False),
    Column('last_login', DateTime, nullable=False),
    Column('date_joined', DateTime, nullable=False),
    Column('new_password_key', String(32), nullable=True),
    Column('banned_until', DateTime, nullable=True),
    # profile attributes
    Column('post_count', Integer, default=0, nullable=False),
    Column('avatar', String(100), nullable=False), # XXX: Use Django to modify that column!
    Column('jabber', String(200), nullable=False),
    Column('icq', String(16), nullable=False),
    Column('msn', String(200), nullable=False),
    Column('aim', String(200), nullable=False),
    Column('yim', String(200), nullable=False),
    Column('skype', String(200), nullable=False),
    Column('wengophone', String(200), nullable=False),
    Column('sip', String(200), nullable=False),
    Column('signature', Text, nullable=False),
    Column('coordinates_long', nullable=True),
    Column('coordinates_lat', nullable=True),
    Column('location', String(200), nullable=False),
    Column('gpgkey', String(8), nullable=False),
    Column('occupation', String(200), nullable=True),
    Column('interests', String(200), nullable=True),
    Column('website', nullable=False),
    Column('launchpad', String(50), nullable=True),
    Column('_settings', Text, nullable=False),
    Column('_permissions', Integer, default=0, nullable=False),
    # forum attributes
    Column('forum_last_read', Integer, default=0, nullable=False),
    Column('forum_read_status', Text, nullable=False),
    Column('forum_welcome', Text, nullable=False),
    Column('member_title', String(200), nullable=True),
    #XXX: This column is named _primary_group in Django user model but named
    #     differently in database.
    Column('primary_group_id', Integer, ForeignKey('portal_group.id'), nullable=True)
)


user_group_table = Table('portal_user_groups', metadata,
    Column('id', Integer, primary_key=True),
    Column('user_id', Integer, ForeignKey('portal_user.id'), nullable=False),
    Column('group_id', Integer, ForeignKey('portal_group.id'), nullable=False),
)


group_table = Table('portal_group', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(80), nullable=False, unique=True),
    Column('is_public', Boolean, default=1, nullable=False),
    Column('permissions', Integer, default=0, nullable=False),
    Column('icon', String(100), nullable=True) #XXX: Use Django to modify that column!
)

forum_welcomemessage_table = Table('forum_welcomemessage', metadata,
    Column('id', Integer, primary_key=True),
    Column('title', String(120), nullable=False),
    Column('text', Text, nullable=False),
    Column('rendered_text', Text, nullable=False),
)

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
