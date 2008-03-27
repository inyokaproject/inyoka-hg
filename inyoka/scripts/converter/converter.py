#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.converter.converter
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This script converts all data of the old wiki, forum and portal to the new
    inyoka structure.

    :copyright: Copyright 2007-2008 by Benjamin Wiegand, Florian Apolloner.
    :license: GNU GPL.
"""
import re
import sys
from inyoka.conf import settings

WIKI_PATH = '/srv/www/de/wiki'
FORUM_URI = 'mysql://%s:%s@%s/ubuntu_de?charset=utf8' % (settings.DATABASE_USER,
    settings.DATABASE_PASSWORD, settings.DATABASE_HOST)
OLD_PORTAL_URI = 'mysql://root@localhost/ubuntu_de_portal?charset=utf8'
FORUM_PREFIX = 'ubuntu_'
AVATAR_PREFIX = 'portal/avatars'
OLD_ATTACHMENTS = '/tmp/'
try:
    # optional converter config to modify the settings
    from inyoka.scripts.converter_config import *
except:
    pass
sys.path.append(WIKI_PATH)

from os import path
from werkzeug.utils import url_unquote
from django.db import connection, transaction
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.sql import select, func, update
from inyoka.wiki.models import Page as InyokaPage
from inyoka.wiki import bbcode
from inyoka.portal.user import User
from datetime import datetime
users = {}

#: These pages got duplicates because we use a case insensitiva collation
#: now.
#: It's in the format deprecated --> new
PAGE_REPLACEMENTS = {
    'Audioplayer': 'AudioPlayer',
    'Centerim': 'CenterIM',
    'Gnome': 'GNOME',
    'Grub': 'GRUB',
    'XGL': 'Xgl',
    'YaKuake': 'Yakuake',
    'Gedit': 'gedit',
    'StartSeite': 'Startseite',
}

def select_blocks(query, block_size=1000, start_with=0):
    """Execute a query blockwise to prevent lack of ram"""
    # get the table
    table = list(query._table_iterator())[0]
    # get the tables primary key (a little bit hackish)
    key_name = list(table.primary_key)[0].name
    key = table.c[key_name]
    range = (start_with, start_with + block_size)
    failed = 0
    while 1:
        print range
        result = query.where(key.between(*range)).execute()
        i = 0
        for i, row in enumerate(result):
            yield row
        if i == 0:
            failed += 1
            if failed == 10:
                break
        else:
            failed = 0
        range = range[1] + 1, range[1] + block_size


def convert_wiki():
    from MoinMoin.Page import Page
    from MoinMoin.request import RequestCLI
    from MoinMoin.logfile import editlog
    from MoinMoin.wikiutil import version2timestamp
    from inyoka.scripts.converter.create_templates import create
    from _mysql_exceptions import IntegrityError
    try:
        create()
    except IntegrityError:
        print 'wiki templates are already created'

    from inyoka.scripts.converter.wiki_formatter import InyokaFormatter, \
            InyokaParser
    from inyoka.wiki.utils import normalize_pagename
    request = RequestCLI()
    formatter = InyokaFormatter(request)
    request.formatter = formatter
    new_page = None
    #us = User.objects.all()
    #for u in us:
    #    users[u.username] = u
    #del us
    import cPickle
    f = file('pagelist', 'r')
    l = cPickle.load(f)
    f.close()
    #start = False
    transaction.enter_transaction_management()
    transaction.managed(True)
    #for i, moin_name in enumerate(l):
    #for i, moin_name in enumerate(request.rootpage.getPageList()):
    for i, moin_name in enumerate(['ATI-Grafikkarten', 'ATI-Grafikkarten/fglrx', 'fglrx']):
        if moin_name in PAGE_REPLACEMENTS:
            # ignore these pages (since gedit equals Gedit in inyoka these
            # pages are duplicates)
            continue
        name = normalize_pagename(moin_name)
        page = Page(request, moin_name, formatter=formatter)
        request.page = page
        for line in editlog.EditLog(request, rootpagename=name):
            connection.queries = []
            rev_id = line.rev
            kwargs = {
                'note': line.comment,
                'change_date': datetime.fromtimestamp(version2timestamp(
                                                     line.ed_time_usecs)),
                'update_meta': False
            }
            data = line.getEditorData(request)
            if data[1] in users:
                kwargs['user'] = users[data[1]]
                kwargs['remote_addr'] = line.addr
            else:
                kwargs['remote_addr'] = data[1]
                kwargs['user'] = User.objects.get_anonymous_user()

            if line.action in ('SAVE', 'SAVENEW', 'SAVE/REVERT'):
                try:
                    f = file(page.get_rev(rev=int(line.rev))[0])
                    text = f.read().decode('utf-8')
                    f.close()
                except IOError:
                    new_page.edit(deleted=True, **kwargs)
                if int(rev_id) == 1:
                    try:
                        new_page = InyokaPage.objects.create(name, text=text,
                                                             **kwargs)
                    except IntegrityError, e:
                        # TODO
                        name = u'DuplicatePages/%s' % name
                        new_page = InyokaPage.objects.create(name, text=text,
                                                             **kwargs)
                else:
                    new_page.edit(text=text, deleted=False, **kwargs)
            elif line.action == 'ATTNEW':
                att = url_unquote(line.extra)
                att_name = '%s/%s' % (name, att)
                pth = path.join(page.getPagePath(), 'attachments', att)
                try:
                    f = file(pth)
                    kwargs = dict(
                        attachment=f.read(),
                        attachment_filename=att,
                        **kwargs
                    )
                except IOError:
                    # attachment file doesn't exist anymore (moinmoin doesn't
                    # keep deleted attachments)
                    continue
                try:
                    att_page = InyokaPage.objects.get(name=att_name)
                except InyokaPage.DoesNotExist:
                    InyokaPage.objects.create(att_name, u'', **kwargs)
                else:
                    att_page.edit(**kwargs)
                f.close()
            elif line.action == 'ATTDEL':
                att = line.extra
                try:
                    att_page = InyokaPage.objects.get(name='%s/%s' % (name,
                                                                      att))
                except InyokaPage.DoesNotExist:
                    continue
                att_page.edit(deleted=True, **kwargs)
            elif line.action == 'ATTDRW':
                pass
            else:
                raise NotImplementedError(line.action)

        # edit the wiki page for syntax converting
        formatter.setPage(page)
        formatter.inyoka_page = new_page
        parser = InyokaParser(text, request)
        text = request.redirectedOutput(parser.format, formatter)
        new_page.edit(text=text, user=User.objects.get_system_user(),
                      note=u'Automatische Konvertierung auf neue Syntax')
        transaction.commit()


def convert_users():
    from _mysql_exceptions import IntegrityError
    from inyoka.wiki import bbcode
    engine = create_engine(FORUM_URI, echo=False, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    conn = engine.connect()
    users_table = Table('%susers' % FORUM_PREFIX, meta, autoload=True)
    odd_coordinates = []
    mail_error = []
    for row in select_blocks(users_table.select()):
        avatar = ''
        co_long = co_lat = None
        if row.user_avatar != '':
            avatar = "%s/%s" % (AVATAR_PREFIX.rstrip('/'), row.user_avatar)
        if row.user_coordinates != '':
            co = row.user_coordinates.split(',')
            try:
                co_long = float(co[1])
                co_lat = float(co[0])
            except (IndexError, ValueError):
                odd_coordinates.append(row.user_id)
                co_long = co_lat = None
        signature = ''
        if row.user_sig_bbcode_uid:
            signature = bbcode.parse(row.user_sig.replace(
                    ':%s' % row.user_sig_bbcode_uid,'')
                ).to_markup()
        #TODO: Everthing gets truncated, dunno if this is the correct way.
        # This might break the layout...
        data = {
            'pk': row.user_id,
            'username': row.username[:30],
            'email': row.user_email[:50] or '',
            'password': 'md5$%s' % row.user_password,
            'is_active': row.user_active,
            'last_login': datetime.fromtimestamp(row.user_lastvisit),
            'date_joined': datetime.fromtimestamp(row.user_regdate),
            #'new_password_key': None,
            'post_count': row.user_posts,
            # TODO: assure correct location
            'avatar': avatar[:100],
            'icq': row.user_icq[:16],
            'msn': row.user_msnm[:200],
            'aim': row.user_aim[:200],
            'yim': row.user_yim[:200],
            'jabber': row.user_jabber[:200],
            'signature': signature,
            'coordinates_long': co_long,
            'coordinates_lat': co_lat,
            'location': row.user_from[:200],
            #'gpgkey': '',
            'occupation': row.user_occ[:200],
            'interests': row.user_interests[:200],
            'website': row.user_website[:200],
            #TODO:
            #'forum_last_read'
            #'forum_read_status'
            #'forum_welcome'
        }
        # make Anonymous id 1, luckily Sascha is 2 ;)
        # CAUTION: take care if mapping -1 to 1 in posts/topics too
        if row.user_id == -1:
            data['pk'] = 1
        try:
            u = User.objects.create(**data)
        except IntegrityError, e:
            # same email adress, forbidden
            if e.args[1].endswith('key 3'):
                data['email'] = "(%d)%s" % (row.user_id, data['email'])
                u = User.objects.create(**data)
                mail_error.append(row.user_id)
            else:
                print e
                sys.exit(1)
        users[u.username] = u
        connection.queries = []
    #print odd_coordinates, mail_error

    # ban users ;) Really q&d
    ban_table = Table('%sbanlist' % FORUM_PREFIX, meta, autoload=True)
    for ban in conn.execute(ban_table.select(ban_table.c.ban_userid != 0)):
        cursor = connection.cursor()
        cursor.execute("UPDATE portal_user SET is_active=0 WHERE id=%i" % ban[1])

def convert_forum():
    from inyoka.forum.models import Forum, Topic, Post

    engine = create_engine(FORUM_URI, echo=False, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    conn = engine.connect()

    print 'Converting forum structue'
    forums_table = Table('%sforums' % FORUM_PREFIX, meta, autoload=True)
    categories_table = Table('%scategories' % FORUM_PREFIX, meta, autoload=True)
    s = select([forums_table])
    result = conn.execute(s)
    forum_cat_map = {}

    for row in result:
        data = {
            'id': row.forum_id,
            'name': row.forum_name,
            'description': row.forum_desc,
            'position': row.forum_order,
            #TODO
            #'last_post': ,
            'post_count': row.forum_posts,
            'topic_count': row.forum_topics,
        }
        f = Forum(**data)
        f.save()
        forum_cat_map.setdefault(row.cat_id, []).append(f)

    s = select([categories_table])
    result = conn.execute(s)
    for row in result:
        data = {
            'name': row.cat_title,
            'position': row.cat_order,
        }
        old_id = row.cat_id
        cat = Forum(**data)
        cat.save()
        new_id = cat.id
        # assign forums to the correct new category ids...
        for forum in forum_cat_map.get(old_id, []):
            forum.parent_id = new_id
            forum.save()

    print 'Converting topics'
    topic_table = Table('%stopics' % FORUM_PREFIX, meta, autoload=True)
    s = select([topic_table])

    # maybe make it dynamic, but not now ;)
    ubuntu_version_map = {
        0: None,
        1:'4.10', 2:'5.04',
        3:'5.10', 4:'6.04',
        7:'6.10', 8:'7.04',
        10:'7.10', 11:'8.04',
    }
    ubuntu_distro_map = {
        0: None,
        1: 'ubuntu', 2: 'kubuntu',
        3: 'xubuntu', 4: 'edubuntu',
        6: 'kubuntu' # KDE(4) is still kubuntu ;)
    }

    result = conn.execute(s)

    i = 0
    transaction.enter_transaction_management()
    transaction.managed(True)
    for row in result:

        data = {
            'pk': row.topic_id,
            'forum_id': row.forum_id,
            'title': row.topic_title,
            'view_count': row.topic_views,
            'post_count': row.topic_replies + 1,
            # sticky and announce are sticky in inyoka
            'sticky': bool(row.topic_type),
            'solved': bool(row.topic_fixed),
            'locked': row.topic_status == 1,
            'ubuntu_version': ubuntu_version_map.get(row.topic_version),
            'ubuntu_distro': ubuntu_distro_map.get(row.topic_desktop),
            'author_id': row.topic_poster,
            #'first_post_id': row.topic_first_post_id,
            #'last_post_id': row.topic_last_post_id,
        }
        # To work around the overwritten objects.create method...
        t = Topic(**data)
        t.save()
        connection.queries = []
        if i == 500:
            transaction.commit()
            i = 0
        else:
            i += 1


    print 'Converting posts'
    post_table = Table('%sposts' % FORUM_PREFIX, meta, autoload=True)
    post_text_table = Table('%sposts_text' % FORUM_PREFIX, meta,
                            autoload=True)
    s = select([post_table, post_text_table],
               (post_table.c.post_id == post_text_table.c.post_id),
               use_labels=True)
    i = 0
    for row in select_blocks(s):
        text = bbcode.parse(row[post_text_table.c.post_text].replace(':%s' % \
            row[post_text_table.c.bbcode_uid], '')).to_markup()
        cur = connection.cursor()
        cur.execute('''
            insert into forum_post (id, topic_id, text, author_id, pub_date,rendered_text,hidden)
                values (%s,%s,%s,%s,%s,'',False);

        ''', (row[post_table.c.post_id], row[post_table.c.topic_id],
              text, row[post_table.c.poster_id],
              datetime.fromtimestamp(row[post_table.c.post_time])))
        if i == 500:
            connection._commit()
            connection.queries = []
            i = 0
        else:
            i += 1
    print 'fixing forum references'

    DJANGO_URI = '%s://%s:%s@%s/%s' % (settings.DATABASE_ENGINE,
        settings.DATABASE_USER, settings.DATABASE_PASSWORD,
        settings.DATABASE_HOST, settings.DATABASE_NAME)
    dengine = create_engine(DJANGO_URI, echo=False, convert_unicode=True)
    dmeta = MetaData()
    dmeta.bind = dengine
    dconn = dengine.connect()
    dtopic = Table('forum_topic', dmeta, autoload=True)
    dpost = Table('forum_post', dmeta, autoload=True)
    dforum = Table('forum_forum', dmeta, autoload=True)

    subselect_max = select([func.max(dpost.c.id)], dtopic.c.id == dpost.c.topic_id)
    subselect_min = select([func.min(dpost.c.id)], dtopic.c.id == dpost.c.topic_id)
    dconn.execute(dtopic.update(values={dtopic.c.last_post_id: subselect_max,
                                        dtopic.c.first_post_id: subselect_min}))
    subselect = select([func.max(dtopic.c.last_post_id)],
                       dtopic.c.forum_id == dforum.c.id)
    dconn.execute(dforum.update(values={dforum.c.last_post_id: subselect}))
    dconn.close()

    conn.close()

    # Fix anon user:
    cur = connection.cursor()
    cur.execute("UPDATE forum_topic SET author_id = 1 WHERE author_id = -1;")
    cur.execute("UPDATE forum_post SET author_id = 1 WHERE author_id = -1;")
    connection._commit()

def convert_groups():
    from inyoka.portal.user import Group

    engine = create_engine(FORUM_URI, echo=False, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    conn = engine.connect()

    group_table = Table('%sgroups' % FORUM_PREFIX, meta, autoload=True)

    sel = select([group_table], group_table.c.group_description != "Personal User")
    for group in conn.execute(sel):
        Group.objects.create(**{
                'pk': group.group_id,
                'name': group.group_name,
                'is_public': True
            })

    relation_table = Table('%suser_group' % FORUM_PREFIX, meta, autoload=True)

    subselect = select([group_table.c.group_id], group_table.c.group_description != "Personal User")
    sel_relation = select([relation_table], relation_table.c.group_id.in_(subselect))

    DJANGO_URI = '%s://%s:%s@%s/%s' % (settings.DATABASE_ENGINE,
        settings.DATABASE_USER, settings.DATABASE_PASSWORD,
        settings.DATABASE_HOST, settings.DATABASE_NAME)
    dengine = create_engine(DJANGO_URI, echo=False, convert_unicode=True)
    dmeta = MetaData()
    dmeta.bind = dengine
    dconn = dengine.connect()
    django_user_group_rel = Table('portal_user_groups', dmeta, autoload=True)

    for erg in conn.execute(sel_relation):
        ins = django_user_group_rel.insert(values={'user_id': erg.user_id, 'group_id': erg.group_id})
        dconn.execute(ins)

    dconn.close()
    conn.close()


def convert_polls():
    from inyoka.forum.models import Poll, PollOption, Voter, Topic

    engine = create_engine(FORUM_URI, echo=False, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    conn = engine.connect()

    poll_table = Table('%svote_desc' % FORUM_PREFIX, meta, autoload=True)
    poll_opt_table = Table('%svote_results' % FORUM_PREFIX, meta, autoload=True)
    voter_table = Table('%svote_voters' % FORUM_PREFIX, meta, autoload=True)

    topics_with_poll = []

    # Only < 10000 Polls, one transaction...
    transaction.enter_transaction_management()
    transaction.managed(True)
    for row in select_blocks(poll_table.select()):
        data = {
            'pk': row.vote_id,
            'question': row.vote_text,
            'start_time': datetime.fromtimestamp(row.vote_start),
            'topic_id': row.topic_id,
        }
        if row.vote_length == 0:
            data['end_time'] = None
        else:
            data['end_time'] = datetime.fromtimestamp(row.vote_start + row.vote_length)
        poll = Poll(**data)
        try:
            poll.save()
        except Topic.DoesNotExist:
            poll.topic_id = None
            poll.save()
        topics_with_poll.append(row.topic_id)
    transaction.commit()

    # Only < 10000 Options, one transaction...
    # Can't use select_blocks, no primary key :/
    for row in conn.execute(poll_opt_table.select()):
        data = {
            'poll_id': row.vote_id,
            'name': row.vote_option_text,
            'votes': row.vote_result
        }
        PollOption.objects.create(**data)
        connection.queries = []
    transaction.commit()

    i = 0
    for row in conn.execute(voter_table.select()):
        data = {
            'voter_id': row.vote_user_id,
            'poll_id': row.vote_id,
        }
        try:
            Voter.objects.create(**data)
        # Some votes are missing polls...
        except:
            pass
        connection.queries = []
        if i == 1000:
            transaction.commit()
            i = 0
        else:
            i += 1

    # Fixing Topic.has_poll
    DJANGO_URI = '%s://%s:%s@%s/%s' % (settings.DATABASE_ENGINE,
        settings.DATABASE_USER, settings.DATABASE_PASSWORD,
        settings.DATABASE_HOST, settings.DATABASE_NAME)
    dengine = create_engine(DJANGO_URI, echo=False, convert_unicode=True)
    dmeta = MetaData()
    dmeta.bind = dengine
    dconn = dengine.connect()

    topic_table = Table('forum_topic', dmeta, autoload=True)
    dconn.execute(topic_table.update(topic_table.c.id.in_(topics_with_poll)),
            has_poll=True)

    # Fix anon user:
    connection.execute("UPDATE forum_voter SET voter_id=1 WHERE voter_id=-1;")


def convert_privileges():
    from inyoka.forum.models import Privilege, Group

    engine = create_engine(FORUM_URI, echo=False, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    conn = engine.connect()

    transaction.enter_transaction_management()
    transaction.managed(True)

    auth_table = Table('%sauth_access' % FORUM_PREFIX, meta, autoload=True)
    for row in conn.execute(auth_table.select()):
        data = {
            'group_id': row.group_id,
            'forum_id': row.forum_id,
            'can_read': bool(row.auth_read),
            'can_reply': bool(row.auth_reply),
            'can_create': bool(row.auth_post),
            'can_edit': bool(row.auth_edit),
            'can_revert': bool(row.auth_mod),
            'can_delete': bool(row.auth_delete),
            'can_sticky': bool(row.auth_sticky) or bool(row.auth_announce),
            'can_vote': bool(row.auth_vote),
            'can_create_poll': bool(row.auth_pollcreate),
            'can_upload': bool(row.auth_attachments),
            'can_moderate': bool(row.auth_mod)
        }
        try:
            Group.objects.get(pk=row.group_id)
        except: continue
        Privilege.objects.create(**data)
    transaction.commit()


def convert_subscriptions():
    from inyoka.portal.models import Subscription

    engine = create_engine(FORUM_URI, echo=False, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    conn = engine.connect()

    subscription_table = Table('%stopics_watch' % FORUM_PREFIX, meta, autoload=True)

    transaction.enter_transaction_management()
    transaction.managed(True)
    # According to http://www.phpbbdoctor.com/doc_columns.php?id=22
    # we need to add both notify_status = 1|0 to out watch_list.
    for row in conn.execute(subscription_table.select()):
        try:
            Subscription.objects.create(user_id=row.user_id, topic_id=row.topic_id)
        # Ignore missing topics...
        except:
            pass
    transaction.commit()


def convert_attachments():
    from inyoka.forum.models import Attachment, Post
    from sqlalchemy.sql import and_


    engine = create_engine(FORUM_URI, echo=False, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    conn = engine.connect()

    attachment_desc_table = Table('%sattachments_desc' % FORUM_PREFIX, meta, autoload=True)
    attachment_table = Table('%sattachments' % FORUM_PREFIX, meta, autoload=True)

    sel = select([attachment_desc_table, attachment_table.c.post_id], \
          and_(attachment_table.c.attach_id == attachment_desc_table.c.attach_id,\
          attachment_table.c.post_id != 0))

    path = OLD_ATTACHMENTS.rstrip('/') + '/'

    transaction.enter_transaction_management()
    transaction.managed(True)
    for row in select_blocks(sel):
        data = {
            'pk': row.attach_id,
            'name': row.real_filename,
            'comment': row.comment,
            'post_id': row.post_id,
        }
        att = Attachment(**data)
        file_ = open(path + row.physical_filename,'rb')
        att.save_file_file(row.real_filename, file_.read())
        file_.close()
        try:
            att.save()
        except Post.DoesNotExist:
            pass
    transaction.commit()


def convert_privmsgs():
    from inyoka.portal.models import PrivateMessage, PrivateMessageEntry
    from sqlalchemy.sql import and_

    engine = create_engine(FORUM_URI, echo=False, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    conn = engine.connect()
    try:
        conn.execute("ALTER TABLE `%sprivmsgs` ADD `done` BOOL NOT NULL DEFAULT '0';" % FORUM_PREFIX)
    except:
        conn.execute("UPDATE `%sprivmsgs` SET `done` = 0 WHERE 1;" % FORUM_PREFIX)

    msg_text_table = Table('%sprivmsgs_text' % FORUM_PREFIX, meta, autoload=True)

    transaction.enter_transaction_management()
    transaction.managed(True)
    i = 0
    FOLDER_MAPPING = {
        0: 1,
        1: 0,
        2: 0,
        3: 3,
        4: 3,
        5: 1,
    }

    msg_table = Table('%sprivmsgs' % FORUM_PREFIX, meta, autoload=True)
    while True:
        msg = conn.execute(msg_table.select(msg_table.c.done==False).limit(1)).fetchone()
        if msg is None:
            break
        ids = [msg.privmsgs_id]
        msg_text = conn.execute(msg_text_table.select(
                    msg_text_table.c.privmsgs_text_id == msg.privmsgs_id)
                   ).fetchone()

        # msg_text missing?
        if msg_text is None:
            print "msg_text missing for %s" % msg.privmsgs_id
            conn.execute(msg_table.update(msg_table.c.privmsgs_id.in_(ids)),
                         done=True)
            continue

        other_msg = conn.execute(msg_table.select(and_(
                                msg_table.c.privmsgs_from_userid ==
                                msg.privmsgs_from_userid,
                                msg_table.c.privmsgs_date == msg.privmsgs_date,
                                msg_table.c.privmsgs_id != msg.privmsgs_id)
                    ).limit(1)).fetchone()

        m = PrivateMessage()
        m.author_id = msg.privmsgs_from_userid;
        m.subject = msg.privmsgs_subject
        m.pub_date = datetime.fromtimestamp(msg.privmsgs_date)
        m.text = bbcode.parse(msg_text.privmsgs_text.replace(':%s' % \
            msg_text.privmsgs_bbcode_uid, '')).to_markup()
        m.save()

        # If the status is sent, the first user is the sender.
        if msg.privmsgs_type in (1, 2, 4):
            user = msg.privmsgs_from_userid
            second_user = msg.privmsgs_to_userid
        # Else the Recipient is the user for the first message.
        # This only happens if the sender deletes his message.
        else:
            user = msg.privmsgs_to_userid
            second_user = msg.privmsgs_from_userid

        m1 = PrivateMessageEntry()
        m1.message = m
        m1.user_id = user
        m1.read = msg.privmsgs_type != 5
        m1.folder = FOLDER_MAPPING[msg.privmsgs_type]
        m1.save()

        m2 = PrivateMessageEntry()
        m2.message = m
        m2.user_id = second_user
        if other_msg is None: # Then the message is deleted
            m2.read = True
            m2.folder = None
            # Except if the type is 1 (for 'Postausgang'), where no copy exists;
            # We put one in the users inbox, and mark it unread
            if msg.privmsgs_type == 1:
                m2.read = False
                m2.folder = 1
        else:
            m2.read = other_msg.privmsgs_type != 5
            m2.folder = FOLDER_MAPPING[other_msg.privmsgs_type]
            ids.append(other_msg.privmsgs_id)

        m2.save()

        conn.execute(msg_table.update(msg_table.c.privmsgs_id.in_(ids)), done=True)

        if i == 500:
            print msg.privmsgs_id
            transaction.commit()
            i = 0
        else:
            i += 1
    transaction.commit()

def convert_ikhaya():
    import re
    from textile import textile
    from markdown import markdown
    from xml.sax import saxutils
    from inyoka.ikhaya.models import Article, Category

    def linebreaks(value):
        """
        Converts newlines into <p> and <br />s.
        Copied of the old portal.
        """
        value = re.sub(r'\r\n|\r|\n', '\n', value) # normalize newlines
        paras = re.split('\n{2,}', value)
        paras = ['<p>%s</p>' % p.strip().replace('\n', '<br />') for p in paras]
        return '\n\n'.join(paras)

    def render_article(text, parser):
        """
        Copied of the old portal.
        """
        if not text.strip():
            return u''
        # TODO: Parse images
        if parser == 'markdown':
            return markdown(text)
        if parser == 'textile':
            return textile(text.encode('utf-8')).decode('utf-8')
        if parser == 'autobr':
            return linebreaks(text)
        if parser == 'xhtml':
            return text
        return saxutils.escape(text)

    engine = create_engine(OLD_PORTAL_URI)
    meta = MetaData()
    meta.bind = engine
    category_table = Table('ikhaya_categories', meta, autoload=True)
    article_table = Table('ikhaya_entries', meta, autoload=True)
    icon_table = Table('static_images', meta, autoload=True)
    user_table = Table('auth_users', meta, autoload=True)

    # contains a mapping of old_user_id -> new_user_id
    user_mapping = {}
    force = {
        'tux123': 'tux21b',
    }
    for user in select_blocks(user_table.select()):
        if user.username in force:
            name = force[user.username]
        else:
            name = user.username
        try:
            user_mapping[user.id] = User.objects.get(username=name).id
        except User.DoesNotExist:
            print u'Not able to find user', name, u'using anonymous instead'
            user_mapping[user.id] = 1

    category_mapping = {}
    for data in category_table.select().execute():
        category = Category(name=data.name)
        category.save()
        category_mapping[data.id] = category

    for data in article_table.select().execute():
        article = Article(
            subject=data.subject,
            pub_date=data.pub_date,
            author_id=user_mapping[data.author_id],
            intro=render_article(data.intro, data.parser),
            text=render_article(data.text, data.parser),
            public=data.public,
            category=category_mapping[data.category_id],
            is_xhtml=1
        )
        article.save()
        connection.queries = []


def convert_pastes():
    from inyoka.pastebin.models import Entry
    from pygments.lexers import get_all_lexers
    engine = create_engine(OLD_PORTAL_URI)
    meta = MetaData()
    meta.bind = engine
    paste_table = Table('paste_pastes', meta, autoload=True)
    mapping = {
        'xhtml': 'html',
        'php': 'html+php',
        'py': 'python',
        'pl': 'perl'
    }
    anonymous = User.objects.get_anonymous_user()
    lexers = []
    for lexer in get_all_lexers():
        lexers.extend(lexer[1])
    for paste in select_blocks(paste_table.select()):
        lang = mapping.get(paste.language, paste.language)
        if not lang or lang not in lexers:
            lang = 'text'
        Entry(
            title=u'kein Titel',
            lang=lang,
            code=paste.code,
            pub_date=paste.date,
            author=anonymous,
            id=paste.id
        ).save()
        connection.queries = []



MODE_MAPPING = {
        'users': convert_users,
        'wiki': convert_wiki,
        'ikhaya': convert_ikhaya,
        'pastes': convert_pastes,
        'groups': convert_groups,
        'forum': convert_forum,
        'subscriptions': convert_subscriptions,
        'privileges': convert_privileges,
        'polls': convert_polls,
        'attachments': convert_attachments,
        'privmsgs': convert_privmsgs,
}

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        for mode in sys.argv[1:]:
            if mode in MODE_MAPPING:
                print 'Converting %s' % mode
                MODE_MAPPING[mode]()
            else:
                print 'Please choose or more of: %s' % ', '.join(MODE_MAPPING)
                sys.exit(1)
            sys.exit(0)
    print 'Converting users'
    convert_users()
    print 'Converting wiki data'
    convert_wiki()
    print 'Converting ikhaya data'
    convert_ikhaya()
    print 'Converting pastes'
    convert_pastes()
    print 'Converting groups'
    convert_groups()
    print 'Converting forum data'
    convert_forum()
    print 'Converting subscriptions'
    convert_subscriptions()
    print 'Converting privileges'
    convert_privileges()
    print 'Converting polls'
    convert_polls()
    print 'Converting attachments'
    convert_attachments()
    print 'Converting private messages'
    convert_privmsgs()
