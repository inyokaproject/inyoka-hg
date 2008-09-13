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
import re
from os import path
from itertools import izip
from os.path import dirname, join, exists
from inyoka.conf import settings
from sqlalchemy import Table
from shutil import move


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


def create_initial_revision(m):
    """
    Created the initial revision for the applications and create the
    migration information table as well as the anonymous user and
    the default group for registered users.
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

    for post in select_blocks(post_table.select(), post_table.c.id):
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


def drop_foreign_key(m, table, column):
    # we have to do this strange thing here because mysql can't just drop
    # columns that are a foreign key.
    # see http://casey.shobe.info/documents/mysql_limitations/ for further
    # details.
    r = m.engine.execute('''
        SHOW CREATE TABLE %s;
    '''% table).fetchone()[1]
    constraint = re.findall('%s_[^`]+' % column, r)[0]
    m.engine.execute('ALTER TABLE `%s` DROP FOREIGN KEY %s;' % \
                     (table, constraint))


def add_foreign_key(m, table, column, target):
    m.engine.execute('''
        ALTER TABLE `%s` ADD FOREIGN KEY (%s) REFERENCES %s
    ''' % (table, column, target))


def add_staticfile(m):
    media_folder = path.join(path.dirname(__file__), 'media')
    try:
        move(path.join(media_folder, 'ikhaya', 'icons'),
             path.join(media_folder, 'portal', 'files'))
    except (IOError, OSError):
        pass

    m.engine.execute('''
        ALTER TABLE `ikhaya_icon` RENAME TO `portal_staticfile`,
                     ADD COLUMN `is_ikhaya_icon` TINYINT(1)  NOT NULL,
                     CHANGE COLUMN `img` `file` VARCHAR(100);
    ''')
    drop_foreign_key(m, 'ikhaya_category', 'icon_id')
    drop_foreign_key(m, 'ikhaya_article', 'icon_id')
    add_foreign_key(m, 'ikhaya_category', 'icon_id', 'portal_staticfile(id)')
    add_foreign_key(m, 'ikhaya_article', 'icon_id', 'portal_staticfile(id)')


def remove_unused_topic_column(m):
    drop_foreign_key(m, 'forum_topic', 'ikhaya_article_id')
    m.engine.execute('''
        ALTER TABLE `forum_topic` DROP COLUMN `ikhaya_article_id`;
    ''')


def add_member_title(m):
    """Add the member title"""
    m.engine.execute('''
        alter table portal_user
            add column member_title varchar(100) after is_ikhaya_writer;
    ''')


def remove_unused_is_public(m):
    """Remove the unused is_public column from the group model"""
    m.engine.execute('''
        alter table portal_group
            drop column is_public;
    ''')


def add_group_icon_cfg(m):
    """Add the config value for the team icon to the storage"""
    _set_storage(m, {
        'team_icon': '',
    })


def add_ikhaya_suggestion_owner(m):
    """Add a owner of a ikhaya suggestion"""
    m.engine.execute('''
        alter table ikhaya_suggestion
            add column owner_id int(11) null after intro;
    ''')


def add_newtopic_default_text(m):
    """Add a default text for a new topic"""
    m.engine.execute('''
        alter table forum_forum
            add column newtopic_default_text text null after welcome_message_id;
    ''')


def add_launchpad_nick(m):
    """Adds the launchpad nickname to the users' profile"""
    m.engine.execute('''
        alter table portal_user
            add column launchpad varchar(50) after website;
    ''')


def add_indices(m):
    m.engine.execute('''
        create index viewforum on forum_topic (forum_id, sticky, last_post_id);
    ''')


def update_post_table(m):
    post_table = Table('forum_post', m.metadata, autoload=True)
    post_text_table = Table('forum_post_text', m.metadata, autoload=True)

    m.engine.execute('''
        ALTER TABLE forum_post ADD `text` longtext, ADD `rendered_text` longtext;
    ''')

    for post in select_blocks(post_text_table.select(), post_table.c.id):
        m.engine.execute(post_table.update(post_table.c.id == post.id, values={
            'text':          post.text,
            'rendered_text': post.rendered_text,
        }))

    m.engine.execute('''
        create index viewtopic on forum_post (topic_id, id);
    ''')

    m.engine.execute('''
        DROP TABLE forum_post_text;
    ''')


def add_position_column(m):
    topic_table = Table('forum_topic', m.metadata, autoload=True)

    m.engine.execute('''
        alter table forum_post
            add column position integer not null after id,
            drop index viewtopic,
            add index viewtopic (topic_id, position);
    ''')

    for topic in select_blocks(topic_table.select(), topic_table.c.id):
        m.engine.execute('''set @rownum:=0;''')
        m.engine.execute('''
            update forum_post set position=(@rownum:=@rownum+1)
                              where topic_id=%s order by id;
        ''', [topic.id])

    # remove some senseless indices
    m.engine.execute('''
        alter table forum_topic
            drop index forum_topic_forum_id,
            drop index forum_topic_reporter_id,
            drop index forum_topic_author_id;
    ''')


def add_permissions(m):
    m.engine.execute('''
        alter table portal_user
            add column _permissions integer not null default 0,
            drop column is_ikhaya_writer,
            drop column is_manager;

    ''')
    m.engine.execute('''
        alter table portal_group
            add column permissions integer not null default 0;
    ''')


def add_post_pub_date_index(m):
    m.engine.execute('''
        alter table forum_post add index forum_post_pub_date (pub_date);
    ''')


def drop_comment_title_column(m):
    m.engine.execute('''
        alter table ikhaya_comment drop column title;
    ''')


def add_new_page_root_storage(m):
    _set_storage(m, {
        'wiki_newpage_template':    u'',
        'wiki_newpage_root':        'Baustelle'
    })


def add_ikhaya_comment_deleted_column(m):
    m.engine.execute('''
        alter table ikhaya_comment
            add column deleted bool not null default 0;
    ''')


def change_forum_post_position_column(m):
    m.engine.execute('''
        alter table forum_post
            modify column position integer not null default 0;
    ''')


# XXX: unused
def add_forum_atime_column(m):
    m.engine.execute('''
        alter table forum_post
            add column atime datetime null default null;
    ''')


def add_wiki_text_html_render_instructions(m):
    m.engine.execute('''
        alter table wiki_text
            add column html_render_instructions longtext default null;
    ''')


def new_team_icon_system(m):
    """
    This migration is used to integrate a new team icon system.

    It adds a new column `_primary_group_id` to the `portal_user` table
    that references to the primary group of an user so we can add
    a team icon to users with various groups as well.
    Since the `portal_group` table got a new `icon` column every
    team can have it's own team icon now.
    """
    # add the new _primary_group_id column to the portal_user table.
    m.engine.execute('''
        begin;
        alter table portal_user
            add column primary_group_id integer null after _permissions;
        commit;
        alter table portal_user
            add foreign key (primary_group_id) references portal_group(id);
    ''')

    # ensure `MEDIA/portal/teamicons` exists.
    media_path = path.join(settings.MEDIA_ROOT, 'portal', 'team_icons')
    if not exists(media_path):
        os.makedirs(media_path)

    # set new storage items
    _set_storage(m, {
        'team_icon_height': 28,
        'team_icon_width': 38,
    })

    # add icon column to group
    m.engine.execute('''
        alter table portal_group
            add column icon varchar(100) null default null after permissions;
    ''')


def fix_suggestion_owner_to_be_null(m):
    """Fix for #2811 – a suggestion owner can be null"""
    m.engine.execute('''
        alter table ikhaya_suggestion
            modify column owner_id int(11) null default null;
    ''')


def new_user_status(m):
    """
    Replace `user.is_active` by `user.status`. rename user.banned to
    banned_until, because the status of being banned is now saved as `status`.
    Set status to 2 if user is banned.
    """
    m.engine.execute('''
        BEGIN;
        ALTER TABLE portal_user
            CHANGE COLUMN is_active status tinyint(1) NOT NULL DEFAULT 0,
            CHANGE COLUMN banned banned_until datetime default NULL;
        COMMIT;
        UPDATE portal_user
            SET status = 2
            WHERE banned_until;
    ''')


def add_post_has_revision(m):
    """
        Add a column `has_revision` to posts. This is to only show the
    'show revisions' link when there actually are revisions.
    """
    m.engine.execute('''
        BEGIN;
        ALTER TABLE forum_post
            ADD COLUMN `has_revision` TINYINT(1) NOT NULL DEFAULT 0 AFTER rendered_text;
        COMMIT;
    ''')


def split_ikhaya_slug(m):
    """
    This migration seperates the ikhaya slug column and deletes
    datetime values from it.
    """
    article_table = Table('ikhaya_article', m.metadata, autoload=True)

    m.engine.execute('''
        begin;
        alter table ikhaya_article
            add column pub_time time not null after pub_date,
            modify column slug varchar(100) not null;
        commit;
        alter table ikhaya_article
            drop index slug,
            add unique (pub_date, slug);
        create index viewarticle on ikhaya_article(slug, pub_date);
    ''')

    for article in select_blocks(article_table.select(), article_table.c.id, 100):
        m.engine.execute(article_table.update(
            article_table.c.id == article.id, values={
                'pub_time': article.pub_date.time(),
                'pub_date': article.pub_date.date(),
                'slug':     article.slug.split('/')[-1]
        }))

    m.engine.execute('''
        alter table ikhaya_article
            modify column pub_date date not null;
    ''')


def add_wiki_revision_foreign_keys(m):
    """Adds foreign keys to the wiki revision table which we forgot to do
    earlier for reasons I don't know.
    """
    m.engine.execute('''
        begin;
            delete from wiki_revision.* from wiki_revision
                left join wiki_text
                    on wiki_revision.text_id = wiki_text.id
                where wiki_text.id is null;

            update wiki_revision set wiki_revision.user_id = 1
                left join portal_user
                    on wiki_revision.user_id = portal_user.id
                where portal_user.id is null;
        commit;

        alter table wiki_revision
            add constraint wiki_revision_text_id_fk
                foreign key wiki_revision_text_id_fk (text_id)
                references wiki_text (id)
                on delete restrict
                on update restrict,
            add constraint wiki_revision_user_id_fk
                foreign key wiki_revision_user_id_fk (user_id)
                references portal_user (id)
                on delete restrict
                on update restrict;
    ''')


def fix_forum_poll_foreign_keys(m):
    """Adds foreign keys that are defined in our database definitions
    (django, sqlalchemy) but are not in the database"""
    m.engine.execute('''
        begin;
            delete forum_poll.* from forum_poll
                left join forum_topic
                    on forum_poll.topic_id = forum_topic.id
                where forum_topic.id is null;

            delete forum_polloption.* from forum_polloption
                left join forum_poll
                    on forum_polloption.poll_id = forum_poll.id
                where forum_poll.id is null;
        commit;

        alter table forum_poll
            add constraint forum_poll_topic_id_fk
                foreign key forum_poll_topic_id_fk(topic_id)
                references forum_topic(id)
                on delete restrict
                on update restrict;

        alter table forum_polloption
            add constraint forum_polloption_poll_id_fk
                foreign key forum_polloption_poll_id_fk(poll_id)
                references forum_poll(id)
                on delete restrict
                on update restrict;

        create index poll_topic_id on forum_poll(topic_id);
    ''')


def fix_forum_post_foreign_keys(m):
    # the topic where everything without a topic lands
    r = m.engine.execute('''
        insert into forum_topic (forum_id, author_id, title, sticky, slug, view_count, post_count, solved, locked, hidden, has_poll)
            values (43, 3134, 'Waisenposts', 1, 'waisenposts', 0, 0, 0, 0, 0, 0);
    ''')
    STASH_ID = int(r.lastrowid)
    m.engine.execute('''
        begin;
            update forum_post set forum_post.topic_id = %d
                left join forum_topic
                    on forum_post.topic_id = forum_topic.id
                where forum_topic.id is null;

            update forum_post set forum_post.author_id = 1
                left join portal_user
                    on forum_post.author_id = portal_user.id
                where portal_user.id is null;
        commit;
        begin;
            update forum_topic set post_count = (
                    select count(forum_post.id)
                        from forum_post
                         where forum_topic.id = forum_post.topic_id
                ), first_post_id = (
                    select min(forum_post.id)
                        from forum_post
                         where forum_topic.id = forum_post.topic_id
                ), last_post_id = (
                    select max(forum_post.id)
                        from forum_post
                         where forum_topic.id = forum_post.topic_id
                )
                where forum_topic.id = %d;
        commit;

        alter table forum_post
            add constraint forum_post_author_id_fk
                foreign key forum_post_author_id_fk(author_id)
                references portal_user(id)
                on delete restrict
                on update restrict,
            add constraint forum_post_topic_id_fk
                foreign key forum_post_topic_id_fk(topic_id)
                references forum_topic(id)
                on delete restrict
                on update restrict;
    ''' % (STASH_ID, STASH_ID))


def fix_forum_privilege_foreign_keys(m):
    m.engine.execute('''
        begin;
            delete forum_privilege.* from forum_privilege
                left join portal_user
                    on forum_privilege.user_id = portal_user.id
                left join forum_forum
                    on forum_privilege.forum_id = forum_forum.id
                where (portal_user.id is null or
                       forum_forum.id is null) and
                      forum_privilege.group_id is null;
        commit;

        alter table forum_privilege
            add constraint forum_privilege_user_id_fk
                foreign key forum_privilege_user_id_fk(user_id)
                references portal_user(id)
                on delete restrict
                on update restrict,
            add constraint forum_privilege_forum_id_fk
                foreign key forum_privilege_forum_id_fk(forum_id)
                references forum_forum(id)
                on delete restrict
                on update restrict;
    ''')


def fix_forum_topic_foreign_keys(m):
    m.engine.execute('''
        begin;
            delete forum_topic.* from forum_topic
                left join portal_user as user1
                    on forum_topic.author_id = user1.id
                left join portal_user as user2
                    on forum_topic.reporter_id = user2.id
                left join forum_forum
                    on forum_topic.forum_id = forum_forum.id
                where user1.id = null or user1.id = null
                      or forum_forum.id is null;
        commit;

        alter table forum_topic
            add constraint forum_topic_author_id_fk
                foreign key forum_topic_author_id_fk(author_id)
                references portal_user(id)
                on delete restrict
                on update restrict,
            add constraint forum_topic_reporter_id_fk
                foreign key forum_topic_reporter_id_fk(reporter_id)
                references portal_user(id)
                on delete restrict
                on update restrict,
            add constraint forum_topic_forum_id_fk
                foreign key forum_topic_forum_id_fk(forum_id)
                references forum_forum(id)
                on delete restrict
                on update restrict;
    ''')

def fix_forum_voter_foreign_keys(m):
    m.engine.execute('''
        begin;
            delete forum_voter.* from forum_voter
                left join portal_user
                    on portal_voter.voter_id = portal_user.id
                where portal_user.id is null;
        commit;

        alter table forum_voter
            add constraint forum_voter_voter_id_fk
                foreign key forum_voter_voter_id_fk(voter_id)
                references portal_user(id)
                on delete restrict
                on update restrict;
    ''')


def fix_ikhaya_article_foreign_keys(m):
    CATEGORY_ID = 117
    m.engine.execute('''
        begin;
            update ikhaya_article set ikhaya_article.author_id = 1
                left join portal_user
                    on ikhaya_article.author_id = portal_user.id
                where portal_user.id is null;

            update ikhaya_article set ikhaya_article.category_id = %d
                left join ikhaya_category
                    on ikhaya_article.category_id = ikhaya_category.id
                where ikhaya_category.id is null;
        commit;

        alter table ikhaya_article
            add constraint ikhaya_article_author_id_fk
                foreign key ikhaya_article_author_id_fk(author_id)
                references portal_user(id)
                on delete restrict
                on update restrict,
            add constraint ikhaya_article_category_id_fk
                foreign key ikhaya_article_category_id_fk(category_id)
                references ikhaya_category(id)
                on delete restrict
                on update restrict;
    ''' % CATEGORY_ID)


def fix_ikhaya_comment_foreign_keys(m):
    m.engine.execute('''
        begin;
            update ikhaya_comment set ikhaya_comment.author_id = 1
                left join portal_user
                    on ikhaya_comment.author_id = portal_user.id
                where portal_user.id is null;
        commit;

        alter table ikhaya_comment
            add constraint ikhaya_comment_author_id_fk
                foreign key ikhaya_comment_author_id_fk(author_id)
                references portal_user(id)
                on delete restrict
                on update restrict;
    ''')


def fix_ikhaya_suggestion_foreign_keys(m):
    m.engine.execute('''
        begin;
            delete ikhaya_suggestion.* from ikhaya_suggestion
                left join portal_user as uer1
                    on ikhaya_suggestion.owner_id = user1.id
                left join portal_user as user2
                    on ikhaya_suggestion.author_id = user2.id
                where user1.id is null or user2.id is null;
        commit;

        alter table ikhaya_suggestion
            add constraint ikhaya_suggestion_owner_id_fk
                foreign key ikhaya_suggestion_owner_id_fk(owner_id)
                references portal_user(id)
                on delete restrict
                on update restrict,
            add constraint ikhaya_suggestion_author_id_fk
                foreign key ikhaya_suggestion_author_id_fk(author_id)
                references portal_user(id)
                on delete restrict
                on update restrict;
    ''')


def fix_pastebin_entry_foreign_keys(m):
    m.engine.execute('''
        begin;
            update pastebin_entry set pastebin_entry.author_id = 1
                left join portal_user
                    on pastebin_entry.author_id = portal_user.id
                where portal_user.id is null;
        commit;

        alter table pastebin_entry
            add constraint pastebin_entry_author_id_fk
                foreign key pastebin_entry_author_id_fk(author_id)
                references portal_user(id)
                on delete restrict
                on update restrict;
    ''')


def fix_planet_entry_foreign_keys(m):
    m.engine.execute('''
        begin;
            delete planet_entry.* from planet_entry
                left join planet_blog
                    on planet_entry.blog_id = planet_blog.id
                where planet_blog.id is null;
        commit;

        alter table planet_entry
            add constraint planet_entry_blog_id_fk
                foreign key planet_entry_blog_id_fk(blog_id)
                references planet_blog(id)
                on delete restrict
                on update restrict;
    ''')

def fix_portal_event_foreign_keys(m):
    m.engine.execute('''
        begin;
            delete portal_event.* form portal_event
                left join portal_user
                    on portal_event.author_id = portal_user.id
                where portal_user.id is null;
        commit;

        alter table portal_event
            add constraint portal_event_author_id_fk
                foreign key portal_event_author_id_fk(author_id)
                references portal_user(id)
                on delete restrict
                on update restrict;
    ''')


def fix_portal_privatemessageentry_foreign_keys(m):
    m.engine.execute('''
        begin;
            delete portal_privatemessageentry.*
              from portal_privatemessageentry
                left join portal_privatemessage
                    on portal_privatemessageentry.message_id =
                       portal_privatemessage.id
                where portal_privatemessage.id is null;
        commit;

        alter table portal_privatemessageentry
            add constraint portal_messageentry_message_id_fk
                foreign key portal_messageentry_message_id_fk(message_id)
                references portal_privatemessage(id)
                on delete restrict
                on update restrict;
    ''')


def add_egosearch_index(m):
    m.engine.execute('''
        alter table forum_post add index egosearch (topic_id,author_id);
    ''')


def add_planet_hidden(m):
    m.engine.execute('''
        alter table planet_entry
            add column hidden tinyint(1) not null default 0;
    ''')

def add_blog_active_flag(m):
    m.engine.execute('''
        ALTER TABLE planet_blog
            ADD COLUMN active tinyint(1) not null default 1;
    ''')


def forum_plaintext(m):
    """This migration adds a new `plaintext` column to
    the forum_post table so we can use plaintext for users
    who won't use our coool syntax"""
    m.engine.execute('''
        alter table forum_post
            add column is_plaintext bool not null default 0 after has_revision,
            modify column rendered_text longtext null default null;
    ''')


def add_negative_privileges(m):
    m.engine.execute('''
        alter table forum_privilege
            change column `bits` `positive` integer default 0,
            add column `negative` integer default 0;
    ''')

def add_reported_topics_storage(m):
    _set_storage(m, {
        'reported_topics_subscribers': '',
    })

def add_group_is_public_flag(m):
    '''re-add the is_public flag to groups'''
    m.engine.execute('''
        ALTER TABLE portal_group
            ADD COLUMN `is_public` tinyint(1) NOT NULL DEFAULT 1 AFTER name;
    ''')


MIGRATIONS = [
    create_initial_revision, fix_ikhaya_icon_relation_definition,
    add_skype_and_sip, add_subscription_notified_and_forum,
    add_wiki_revision_change_date_index, fix_sqlalchemy_forum,
    new_forum_acl_system, add_attachment_mimetype, new_attachment_structure,
    add_default_storage_values, add_blocked_hosts_storage, split_post_table,
    add_ikhaya_discussion_disabler, fix_forum_text_table, add_staticfile,
    remove_unused_topic_column, add_member_title, remove_unused_is_public,
    add_group_icon_cfg, add_ikhaya_suggestion_owner, add_newtopic_default_text,
    add_launchpad_nick, add_indices, update_post_table, add_position_column,
    add_permissions, add_post_pub_date_index, drop_comment_title_column,
    add_new_page_root_storage, add_ikhaya_comment_deleted_column,
    change_forum_post_position_column, add_wiki_text_html_render_instructions,
    new_team_icon_system, fix_suggestion_owner_to_be_null, new_user_status,
    add_post_has_revision, split_ikhaya_slug, add_wiki_revision_foreign_keys,
    fix_forum_poll_foreign_keys, fix_forum_post_foreign_keys,
    fix_forum_privilege_foreign_keys, fix_forum_topic_foreign_keys,
    fix_forum_voter_foreign_keys, fix_ikhaya_article_foreign_keys,
    fix_ikhaya_comment_foreign_keys, fix_ikhaya_suggestion_foreign_keys,
    fix_pastebin_entry_foreign_keys, fix_planet_entry_foreign_keys,
    fix_portal_event_foreign_keys, fix_portal_privatemessageentry_foreign_keys,
    add_egosearch_index, add_planet_hidden, forum_plaintext,
    add_negative_privileges, add_reported_topics_storage,
    add_group_is_public_flag,
]
