# -*- coding: utf-8 -*-
"""
    inyoka.migrations
    ~~~~~~~~~~~~~~~~~

    Our database migrations.

    This module must never import application code so that migrations
    can work properly for bootstrapping and upgrading.  It may suck but
    you have to use raw sql here or use the tables (which you *must not*
    import but fetch from the m object using the getitem syntax).

    You must not import any code here beside external modules, utils.database
    or utils.migrations.  At least up to the moment where we only have
    SQLAlchemy in use.

    Keep that in mind!

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from itertools import izip
from os.path import dirname, join
from inyoka.conf import settings


SQL_FILES = join(dirname(__file__), 'sql')


OLD_FORUM_PRIVILEGES = ['read', 'reply', 'create', 'edit', 'revert', 'delete',
 'sticky', 'vote', 'create_poll', 'upload', 'moderate']
NEW_FORUM_PRIVILEGES = dict((OLD_FORUM_PRIVILEGES[i-1], i) for i in range(1, 12))
NEW_FORUM_PRIVILEGES['void'] = -1

def join_flags(flags):
    if not flags:
        return 0
    result = 0
    for flag in flags:
        result |= isinstance(flag, basestring) and \
                  NEW_FORUM_PRIVILEGES[flag] or flag
    return result


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


def add_wiki_revision_change_date_index(m):
    """
    This revision added an index on the change date
    """
    m.engine.execute('''
        alter table wiki_revision
            add index wiki_revision_change_date(change_date);
    ''')


def fix_sqlalchemy_forum(m):
    """
    This migration alters some forum tables to match the new
    sqlalchemy layout.
    """
    m.engine.execute('''
        alter table forum_topic change column slug
            slug varchar(50) not null;
    ''')


def new_forum_acl_system(m):
    """
    This migration deletes old columns for the first version
    of our forum-acl-system. The new one just uses some
    bit-magic so we just need one column for all privileges.
    """
    # Collect the old privilege-rows
    items = ', '.join(OLD_FORUM_PRIVILEGES)
    old_rows = dict((r[0], r[1:]) for r in m.engine.execute('''
        select p.id, %s
          from forum_privilege p
    ''' % ', '.join(['can_'+x for x in OLD_FORUM_PRIVILEGES])))

    old_rows = tuple(izip(old_rows.keys(), [
        dict(filter(lambda x: x[1]!=0, izip(OLD_FORUM_PRIVILEGES, r)))
        for x, r in old_rows.iteritems()]))

    # add the new `bits` column
    m.engine.execute('''
        alter table forum_privilege
            add column bits integer after forum_id;
    ''')

    # migrate the values
    for id, privileges in old_rows:
        m.engine.execute('''
            update forum_privilege
               set bits = %d
             where id = %d
        ''' % (join_flags(privileges.keys()), id))

    # and delete the old columns
    m.engine.execute('''
        alter table forum_privilege
            %s;
    ''' % ', '.join(['drop column can_' + x for x in OLD_FORUM_PRIVILEGES]))



MIGRATIONS = [
    create_initial_revision, fix_ikhaya_icon_relation_definition,
    add_skype_and_sip, add_subscription_notified_and_forum,
    add_wiki_revision_change_date_index, fix_sqlalchemy_forum,
    new_forum_acl_system,
]
