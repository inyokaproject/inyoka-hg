# -*- coding: utf-8 -*-
"""
    inyoka.migrations
    ~~~~~~~~~~~~~~~~~

    Our database migrations.

    This module must never import application code so that migrations
    can work properly for bootstrapping and upgrading.  If may suck but
    you have to use raw sql here or use the tables (which you *must not*
    import but fetch from the m object using the getitem syntax).

    You must not import any code here beside external modules, utils.database
    or utils.migrations.  At least up to the moment where we only have
    SQLAlchemy in use.

    Keep that in mind!

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from os.path import dirname, join
from inyoka.conf import settings


SQL_FILES = join(dirname(__file__), 'sql')


def execute_script(con, name):
    """Execute a script on a connectable."""
    f = file(join(SQL_FILES, name))
    try:
        con.execute(f.read())
    finally:
        f.close()


def create_initial_revision(m):
    """
    Created the initial revision for the applications and create the
    migration information table as well as the anonymous user.
    """
    execute_script(m.engine, 'initial.sql')


def fix_ikhaya_icon_relation_definition(m):
    """
    This migration fixed a bug in the Article definition of the ikhaya
    models.
    """
    m.engine.execute('''
        alter table ikhaya_article modify column icon_id integer;
    ''')


def add_skype_and_sip(m):
    """
    This migration added support for skype and SIP profile fields.
    """
    m.engine.execute('''
        alter table portal_user
            add column skype varchar(200) not null after yim,
            add column wengophone varchar(200) not null after skype,
            add column sip varchar(200) not null after wengophone;
    ''')


def add_subscription_notified_and_forum(m):
    """
    This migration added two fields to the subscription table.
    """
    m.engine.execute('''
        begin;
        alter table portal_subscription
            add column forum_id integer null after topic_id,
            add column notified bool not null after wiki_page_id;
        create index portal_subscription_forum_id
            on portal_subscription (forum_id);
        commit;
        alter table portal_subscription
            add constraint forum_id_refs_id_7009f990
                foreign key forum_id_refs_id_7009f990 (forum_id)
                references forum_forum (id);
    ''')


MIGRATIONS = [
    create_initial_revision, fix_ikhaya_icon_relation_definition,
    add_skype_and_sip, add_subscription_notified_and_forum
]
