#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.converter
    ~~~~~~~~~~~~~~~~~~~~~~~~

    This script converts all data of the old wiki, forum and portal to the new
    inyoka structure.

    :copyright: Copyright 2007 by Benjamin Wiegand and Florian Apolloner.
    :license: GNU GPL.
"""
import sys
from django.conf import settings

WIKI_PATH = '/srv/www/de/wiki'
FORUM_URI = 'mysql://%s:%s@%s/ubuntu_de?charset=utf8' % (settings.DATABASE_USER,
#FORUM_URI = 'mysql://%s:%s@%s/phpbb?charset=utf8' % (settings.DATABASE_USER,
    settings.DATABASE_PASSWORD, settings.DATABASE_HOST)
OLD_PORTAL_URI = 'mysql://root@localhost/ubuntu_de_portal?charset=utf8'
FORUM_PREFIX = 'ubuntu_'
#FORUM_PREFIX = 'phpbb_'
AVATAR_PREFIX = 'portal/avatars'
OLD_ATTACHMENTS = '/tmp/'
sys.path.append(WIKI_PATH)

from os import path
from django.db import connection, transaction
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.sql import select, func, update
from inyoka.wiki.models import Page as InyokaPage
from inyoka.wiki import bbcode
from inyoka.portal.user import User
from datetime import datetime
users = {}


def select_blocks(query, block_size=1000):
    """Execute a query blockwise to prevent lack of ram"""
    # get the table
    table = list(query._table_iterator())[0]
    # get the tables primary key (a little bit hackish)
    key_name = list(table.primary_key)[0].name
    key = table.c[key_name]
    range = (0, block_size)
    while True:
        print range
        result = query.where(key.between(*range)).execute()
        i = 0
        for i, row in enumerate(result):
            yield row
        if i == 0:
            break
        range = range[1] + 1, range[1] + block_size


def convert_wiki():
    from MoinMoin.Page import Page
    from MoinMoin.request import RequestCLI
    from MoinMoin.logfile import editlog
    from MoinMoin.wikiutil import version2timestamp
    from MoinMoin.parser.wiki import Parser
    from inyoka.scripts.converter.wiki_formatter import InyokaFormatter
    from inyoka.wiki.utils import normalize_pagename
    from _mysql_exceptions import IntegrityError
    request = RequestCLI()
    formatter = InyokaFormatter(request)
    request.formatter = formatter
    new_page = None
    #import cPickle
    #f = file('pagelist', 'r')
    #l = cPickle.load(f)
    #f.close()
    #for i, moin_name in enumerate(l):
    for i, moin_name in enumerate(request.rootpage.getPageList()):
    #for i, moin_name in enumerate(['Programme starten']):
        name = normalize_pagename(moin_name)
        print i, ':', name
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
                att = line.extra
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
        parser = Parser(text, request)
        text = request.redirectedOutput(parser.format, formatter)
        new_page.edit(text=text, user=User.objects.get_system_user(),
                      note=u'Automatische Konvertierung auf neue Syntax')


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
            avatar = "%s/%s" % (AVATAR_PREFIX.rstrip('/'),row.user_avatar)
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
            'email': row.user_email[:50] or None,
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
                data['email'] = "(%d)%s" % (row.user_id ,data['email'])
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
    f = open("dump-missing-topics", "w")
    post_table = Table('%sposts' % FORUM_PREFIX, meta, autoload=True)
    post_text_table = Table('%sposts_text' % FORUM_PREFIX, meta,
                            autoload=True)
    s = select([post_table, post_text_table],
               (post_table.c.post_id == post_text_table.c.post_id),
               use_labels=True)
    i = 0
    transaction.enter_transaction_management()
    transaction.managed(True)
    for row in select_blocks(s):
        text = bbcode.parse(row[post_text_table.c.post_text].replace(':%s' % \
            row[post_text_table.c.bbcode_uid], '')).to_markup()
        data = {
            'pk': row[post_table.c.post_id],
            'topic_id': row[post_table.c.topic_id],
            'text': text,
            'author_id': row[post_table.c.poster_id],
            'pub_date': datetime.fromtimestamp(row[post_table.c.post_time])
        }
        p = Post(**data)
        try:
            p.save()
        except Topic.DoesNotExist:
            f.write("%s %s %s\n" % (data['pk'],data['topic_id'],data['pub_date']))
            f.flush()
            pass
        connection.queries = []
        if i == 500:
            transaction.commit()
            i = 0
        else:
            i += 1
    f.close()
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
    connection.execute("UPDATE forum_topic SET author_id = 1 WHERE author_id = -1;")
    connection.execute("UPDATE forum_post SET author_id = 1 WHERE author_id = -1;")

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

    engine = create_engine(FORUM_URI, echo=False, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    conn = engine.connect()

    msg_table = Table('%sprivmsgs' % FORUM_PREFIX, meta, autoload=True)
    msg_text_table = Table('%sprivmsgs_text' % FORUM_PREFIX, meta, autoload=True)

    sel = msg_table.select().order_by( msg_table.c.privmsgs_date.asc(),
                                      msg_table.c.privmsgs_from_userid)

    transaction.enter_transaction_management()
    transaction.managed(True)
    from_user = None
    date = None
    last_msg = None
    last_row = None
    msg_count = 1
    first_time = True
    i = 0
    for row in select_blocks(sel):
        last_row = row
        # Create new message, if date/from_user differ from last row.
        if not (row.privmsgs_from_userid == from_user and
            row.privmsgs_date == date):
            date = row.privmsgs_date
            from_user = row.privmsgs_from_userid
            s = select([msg_text_table], msg_text_table.c.privmsgs_text_id == row.privmsgs_id)
            result = conn.execute(s).fetchone()
            # Workaround for no result?!
            if result is None:
                last_msg = None
                continue
            text = bbcode.parse(result.privmsgs_text.replace(':%s' % \
                        result.privmsgs_bbcode_uid, '')).to_markup()
            data = {
                'author_id': row.privmsgs_from_userid,
                'subject': row.privmsgs_subject,
                'pub_date': datetime.fromtimestamp(row.privmsgs_date),
                'text': text
            }
            try:
                pm = PrivateMessage.objects.create(**data)
            except:
                pass
            if msg_count == 1:
                if first_time:
                    last_msg = pm.id
                if last_row.privmsgs_type in (0,5,3):
                    user_id = last_row.privmsgs_from_userid
                else:
                    user_id = last_row.privmsgs_to_userid
                PrivateMessageEntry.objects.create(user_id=user_id, message_id=
                    last_msg, folder=None, read=True)
            else: msg_count = 1
            last_msg = pm.id

        first_time = False

        if (row.privmsgs_from_userid == from_user and
                        row.privmsgs_date == date):
            msg_count += 1

        if last_msg is None:
            continue
        # Create the Message entry:
        data = {
            'message_id': last_msg,
            'read': True,
        }
        # If the message is read/unread put it into inbox and set read flag.
        # The user is the recipient.
        if row.privmsgs_type in (0,5):
            data['read'] = not bool(row.privmsgs_type)
            data['folder'] = 1
            data['user_id'] = row.privmsgs_to_userid
        # If the message is sent/in_outbox put it into sent (0).
        # The user is the sender.
        elif row.privmsgs_type in (1,2):
            # Copy it into the user's Inbox
            if row.privmsgs_type == 1:
                PrivateMessageEntry.objects.create(read=False, folder=1, 
                        user_id=row.privmsgs_to_userid, message_id=last_msg)
                msg_count += 1
            data['folder'] = 0
            data['user_id'] = row.privmsgs_from_userid
        # If the message is saved put it into archive
        # The user depends on the type.
        else:
            data['folder'] = 3
            if row.privmsgs_type == 3:
                data['user_id'] = row.privmsgs_to_userid
            else:
                data['user_id'] = row.privmsgs_from_userid

        try:
            PrivateMessageEntry.objects.create(**data)
        except:
            pass

        if i == 500:
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
    comment_table = Table('ikhaya_comments', meta, autoload=True)
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
        mode = sys.argv[1]
        if mode in MODE_MAPPING:
            print 'Converting only %s' % mode
            MODE_MAPPING[mode]()
            sys.exit(0)
        else:
            print 'Please choose one of: %s' % ', '.join(MODE_MAPPING)
            sys.exit(1)
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
