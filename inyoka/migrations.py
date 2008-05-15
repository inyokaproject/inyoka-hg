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

    :copyright: Copyright 2008 by Armin Ronacher, Christopher Grebs,
                                  Benjamin Wiegand.
    :license: GNU GPL.
"""
import os
from itertools import izip
from os.path import dirname, join, exists
from inyoka.conf import settings
from sqlalchemy import Table


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


def select_blocks(query, block_size=1000, start_with=0, max_fails=10):
    """Execute a query blockwise to prevent lack of ram"""
    # get the table
    table = list(query._table_iterator())[0]
    # get the tables primary key (a little bit hackish)
    key_name = list(table.primary_key)[0].name
    key = table.c[key_name]
    range = (start_with, start_with + block_size)
    failed = 0
    while failed < max_fails:
        result = query.where(key.between(*range)).execute()
        i = 0
        for i, row in enumerate(result):
            yield row
        if i == 0:
            failed += 1
        else:
            failed = 0
        range = range[1] + 1, range[1] + block_size


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


def add_attachment_mimetype(m):
    """Add a new mimetype column to forum_attachment"""
    m.engine.execute('''
        alter table forum_attachment
         add column mimetype varchar(100) after post_id;
    ''')


def new_attachment_structure(m):
    """Moves old attachments to the new filesystem structure"""
    attachment_path = join(settings.MEDIA_ROOT, 'forum', 'attachments')
    if not exists(attachment_path):
        return
    if not exists(join(attachment_path, 'temp')):
        os.mkdir(join(attachment_path, 'temp'))

    attachments = m.engine.execute('''
        select a.id, a.file, a.name, a.post_id
            from forum_attachment a
    ''')
    for row in attachments:
        id, old_fn, name, pid = row
        new_path = join('forum', 'attachments', str(pid))
        new_abs_path = join(settings.MEDIA_ROOT, new_path)

        if not exists(new_abs_path):
            os.mkdir(new_abs_path)

        try:
            old_fo = open(join(settings.MEDIA_ROOT, old_fn), 'r')
        except IOError:
            continue
        new_fo = open(join(new_abs_path, name), 'w')
        try:
            new_fo.write(old_fo.read())
        finally:
            new_fo.close()
            old_fo.close()
        os.remove(join(settings.MEDIA_ROOT, old_fn))

        m.engine.execute('''
            update forum_attachment
                set file = %s
            where id = %s
        ''', (join(new_path, name), id))


def _set_storage(m, values):
    for k, v in values.iteritems():
        r = m.engine.execute('''
            select 1 from portal_storage where `key` = %s
        ''', (k,))
        if not r.fetchone():
            m.engine.execute('''
                insert ignore into portal_storage (`key`, value)
                                           values (%s, %s)
            ''', (k, v))


def add_default_storage_values(m):
    _set_storage(m, {
        'global_message':           '',
        'max_avatar_width':         80,
        'max_avatar_height':        100,
        'max_signature_length':     400,
        'max_signature_lines':      4,
        'get_ubuntu_link':          '',
        'get_ubuntu_description':   '8.04 „Hardy Heron“',
    })


def add_blocked_hosts_storage(m):
    _set_storage(m, {
        'blocked_hosts': ''
    })


def split_post_table(m):
    m.engine.execute('''
        CREATE TABLE forum_post_text (
                id INTEGER NOT NULL AUTO_INCREMENT,
                text TEXT NOT NULL,
                rendered_text TEXT NOT NULL,
                PRIMARY KEY (id)
        )
    ''')

    post_table = Table('forum_post', m.metadata, autoload=True)
    post_text_table = Table('forum_post_text', m.metadata, autoload=True)

    for post in select_blocks(post_table.select()):
        m.engine.execute(post_text_table.insert(values={
            'id':               post.id,
            'text':             post.text,
            'rendered_text':    post.rendered_text
        }))

    m.engine.execute('''
        ALTER TABLE `forum_post` DROP COLUMN `text`,
                                 DROP COLUMN `rendered_text`;
    ''')


def add_ikhaya_discussion_disabler(m):
    m.engine.execute('''
       ALTER TABLE `ikhaya_article` ADD COLUMN `comments_enabled` TINYINT(1)
                                                NOT NULL DEFAULT 1
                                                AFTER `comment_count`;
    ''')


def fix_forum_text_table(m):
    m.engine.execute('''
        ALTER TABLE `forum_post_text` MODIFY COLUMN `text` LONGTEXT,
                                      MODIFY COLUMN `rendered_text` LONGTEXT;
    ''')


MIGRATIONS = [
    create_initial_revision, fix_ikhaya_icon_relation_definition,
    add_skype_and_sip, add_subscription_notified_and_forum,
    add_wiki_revision_change_date_index, fix_sqlalchemy_forum,
    new_forum_acl_system, add_attachment_mimetype, new_attachment_structure,
    add_default_storage_values, add_blocked_hosts_storage, split_post_table,
    add_ikhaya_discussion_disabler, fix_forum_text_table
]
