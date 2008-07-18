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
import cPickle
from os import path, listdir
from datetime import datetime
from werkzeug import unescape
from werkzeug.utils import url_unquote
from _mysql_exceptions import IntegrityError, OperationalError as meOperationalError
from django.db import connection, transaction
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.sql import select, func, and_
from sqlalchemy.exceptions import OperationalError
from inyoka.conf import settings
settings.DEBUG = False
settings.DATABASE_DEBUG = False
from inyoka.forum.acl import join_flags, PRIVILEGES
from inyoka.wiki import bbcode
from inyoka.wiki.models import Page as InyokaPage
from inyoka.wiki.parser import nodes
from inyoka.wiki.parser.transformers import AutomaticParagraphs, Transformer
from inyoka.forum.models import Privilege, Attachment, Topic, \
    Poll, Forum, topic_table as sa_topic_table, forum_table as \
    sa_forum_table, post_table as sa_post_table, poll_vote_table as \
    sa_poll_vote_table, poll_option_table as sa_poll_option_table
from inyoka.portal.models import PrivateMessage, PrivateMessageEntry, \
    Subscription, StaticFile, StaticPage
from inyoka.ikhaya.models import Article, Category
from inyoka.pastebin.models import Entry
from inyoka.utils.database import session
from inyoka.utils.text import normalize_pagename
from inyoka.portal.user import User, Group
from inyoka.scripts.converter.create_templates import create


_account = '%s:%s@%s' % (settings.DATABASE_USER, settings.DATABASE_PASSWORD,
                       settings.DATABASE_HOST)
FORUM_URI = 'mysql://%s/ubuntu_de?charset=utf8' % _account
OLD_PORTAL_URI = 'mysql://%s/ubuntu_de_portal?charset=utf8' % _account
FORUM_PREFIX = 'ubuntu_'
AVATAR_PREFIX = 'portal/avatars'
OLD_ATTACHMENTS = '/nfs/www/de/files_tmp/files'
WIKI_PATH = '/srv/www/de/wiki'
DJANGO_URI = '%s://%s/%s' % (settings.DATABASE_ENGINE, _account,
                             settings.DATABASE_NAME)

try:
    # optional converter config to modify the settings
    from inyoka.scripts.converter_config import *
except ImportError:
    pass

sys.path.append(WIKI_PATH)

#: These pages got duplicates because we use a case insensitiva collation
#: now.
#: It's in the format deprecated --> new
PAGE_REPLACEMENTS = {
    'Audioplayer':  'AudioPlayer',
    'Centerim':     'CenterIM',
    'Gnome':        'GNOME',
    'Grub':         'GRUB',
    'XGL':          'Xgl',
    'YaKuake':      'Yakuake',
    'Gedit':        'gedit',
    'StartSeite':   'Startseite',
    'XFCE':         'Xfce',
    'Gimp':         'GIMP',
}
CATEGORY_RE = re.compile('[\n]+ \* Kategorie/[^\n]+')
IMG_RE = re.compile(r'\[\[(.+?)\]\]')
NOTIFICATION_MAPPING = {
    0: ['mail'],
    1: ['jabber'],
    2: ['mail', 'jabber'],
}


def fix_encoding(text):
    try:
        x = x.encode("latin1").decode("utf-8")
    except:
        pass

def convert_bbcode(text, uid):
    """Parse bbcode, remove the bbcode uid and return inyoka wiki markup"""
    remove = (':1:%s', ':u:%s', ':o:%s', ':%s',)
    for i in remove:
        text = text.replace(i % uid, '')
    tree = bbcode.Parser(text, transformers=[AutomaticParagraphs()]).parse()
    return tree.to_markup(writer=bbcode.BBMarkupWriter())


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


def forum_db():
    engine = create_engine(FORUM_URI, echo=False, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    conn = engine.connect()
    return engine, meta, conn


def fix_encoding(text):
    try:
        return text.encode('latin1').decode('utf-8')
    except UnicodeError:
        return text


def convert_wiki():
    from MoinMoin.Page import Page
    from MoinMoin.request import RequestCLI
    from MoinMoin.logfile import editlog
    from MoinMoin.wikiutil import version2timestamp
    # circular import
    from inyoka.scripts.converter.wiki_formatter import InyokaFormatter, \
        InyokaParser
    try:
        create()
    except IntegrityError:
        print 'wiki templates are already created'

    request = RequestCLI()
    formatter = InyokaFormatter(request)
    request.formatter = formatter
    new_page = None

    users = {}
    for u in User.objects.all():
        users[u.username] = u

    try:
        f = file('pagelist', 'r')
    except IOError:
        page_list = list(request.rootpage.getPageList())
        f = file('pagelist', 'w+')
        cPickle.dump(page_list, f)
        f.close()
    else:
        page_list = cPickle.load(f)
        f.close()

    transaction.enter_transaction_management()
    transaction.managed(True)
    for i, moin_name in enumerate(page_list):
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
                        name = u'DuplicatePages/%s' % name
                        new_page = InyokaPage.objects.create(name, text=text,
                                                             **kwargs)
                else:
                    new_page.edit(text=text, deleted=False, **kwargs)
            elif line.action == 'ATTNEW':
                att = url_unquote(line.extra.encode('utf-8'))
                att_name = normalize_pagename('%s/%s' % (name, att))
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
        if name.startswith('Kategorie/'):
            n = name[10:]
            text = (u'# tag: Kategorie\nSeiten in der Kategorie „%s“:\n'
                   u'[[TagListe(%s)]]') % (n, n)
        elif name == 'Kategorien':
            text = u'Kategorien sind eine Form der Markierung. Es sind keine exklusiven Schubladen, in denen man Artikel verstauen kann, so wie im alten Wiki in einem Namensraum - eher sind es frei kombinierbare Etiketten.\n[[TagListe(Kategorie)]]'
        else:
            formatter.setPage(page)
            formatter.inyoka_page = new_page
            parser = InyokaParser(text, request)
            text = request.redirectedOutput(parser.format, formatter).strip()
            # remove old category links at the bottom of the page.
            # we don't need them anymore since we have tags now
            text = CATEGORY_RE.sub('', text)
            # remove senseless horizontal lines at the bottom of the pages
            if text[-4:] == '----':
                text = text[:-4].strip()
            # add tags to the bottom of the page
            text += formatter.get_tags()
        new_page.edit(text=text, user=User.objects.get_system_user(),
                      note=u'Automatische Konvertierung auf neue Syntax')
        transaction.commit()


def convert_users():
    engine, meta, conn = forum_db()
    users_table = Table('%susers' % FORUM_PREFIX, meta, autoload=True)
    ban_table = Table('%sbanlist' % FORUM_PREFIX, meta, autoload=True)

    odd_coordinates = []
    mail_error = []

    for row in select_blocks(users_table.select()):
        avatar = ''
        co_long = co_lat = None
        if row.user_avatar:
            avatar = "%s/%s" % (AVATAR_PREFIX.rstrip('/'), row.user_avatar)
        if row.user_coordinates:
            co = row.user_coordinates.split(',')
            try:
                co_long = float(co[1])
                co_lat = float(co[0])
            except (IndexError, ValueError):
                odd_coordinates.append(row.user_id)
                co_long = co_lat = None

        signature = ''
        if row.user_sig_bbcode_uid:
            signature = convert_bbcode(unescape(row.user_sig),
                                       row.user_sig_bbcode_uid)

        notify = NOTIFICATION_MAPPING.get(row.user_notify_jabber, [])

        #TODO: Everthing gets truncated, dunno if this is the correct way.
        # This might break the layout...
        data = {
            'pk':               row.user_id,
            'username':         unescape(row.username[:30]),
            'email':            row.user_email[:50] or '',
            'password':         'md5$%s' % row.user_password,
            'is_active':        row.user_active,
            'last_login':       datetime.fromtimestamp(row.user_lastvisit),
            'date_joined':      datetime.fromtimestamp(row.user_regdate),
            'post_count':       row.user_posts,
            # TODO: assure correct location
            'avatar':           avatar[:100],
            'icq':              row.user_icq[:16],
            'msn':              unescape(row.user_msnm[:200]),
            'aim':              unescape(row.user_aim[:200]),
            'yim':              unescape(row.user_yim[:200]),
            'jabber':           unescape(row.user_jabber[:200]),
            'signature':        signature,
            'coordinates_long': co_long,
            'coordinates_lat':  co_lat,
            'location':         unescape(row.user_from[:200]),
            'occupation':       unescape(row.user_occ[:200]),
            'interests':        unescape(row.user_interests[:200]),
            'website':          unescape(row.user_website[:200]),
            '_settings':        cPickle.dumps({'notify': notify}),
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
        connection.queries = []

    print 'Odd coordinates:', odd_coordinates
    print 'Duplicate use of mail adress:', mail_error

    # ban users ;) Really q&d
    for ban in conn.execute(ban_table.select(ban_table.c.ban_userid != 0)):
        cursor = connection.cursor()
        cursor.execute("UPDATE portal_user SET is_active=0 WHERE id=%i" % ban[1])


def convert_forum():
    engine, meta, conn = forum_db()

    categories_table = Table('%scategories' % FORUM_PREFIX, meta,
                             autoload=True)
    forums_table = Table('%sforums' % FORUM_PREFIX, meta, autoload=True)
    topic_table = Table('%stopics' % FORUM_PREFIX, meta, autoload=True)
    post_table = Table('%sposts' % FORUM_PREFIX, meta, autoload=True)
    post_text_table = Table('%sposts_text' % FORUM_PREFIX, meta,
                            autoload=True)

    print 'Converting forum structue'

    forum_cat_map = {}

    for row in conn.execute(select([forums_table])):
        f = Forum(**{
            'id':          row.forum_id,
            'name':        row.forum_name,
            'description': row.forum_desc,
            'position':    row.forum_order,
            'post_count':  row.forum_posts,
            'topic_count': row.forum_topics,
        })
        session.commit()
        forum_cat_map.setdefault(row.cat_id, []).append(f)

    for row in conn.execute(select([categories_table])):
        cat = Forum(**{
            'name': row.cat_title,
            'position': row.cat_order,
        })
        session.commit()

        # assign forums to the correct new category ids...
        for forum in forum_cat_map.get(row.cat_id, []):
            forum.parent_id = cat.id
            session.commit()

    print 'Converting topics'

    # maybe make it dynamic, but not now ;)
    ubuntu_version_map = {
        0: None,
        1:'4.10',
        2:'5.04',
        3:'5.10',
        4:'6.06',
        7:'6.10',
        8:'7.04',
        10:'7.10',
        11:'8.04',
    }
    ubuntu_distro_map = {
        0: None,
        1: 'ubuntu',
        2: 'kubuntu',
        3: 'xubuntu',
        4: 'edubuntu',
        6: 'kubuntu' # KDE(4) is still kubuntu ;)
    }

    forums = {}
    for f in Forum.query.all():
        forums[f.id] = f

    for row in conn.execute(select([topic_table])):
        if row.topic_replies == 1 and row.topic_moved_id > 0:
            # this should match topics with one post that are moved
            # to another one and are now topics with -1 posts :=)
            continue
        t = Topic(**{
            'id':             row.topic_id,
            'forum':          row.forum_id in forums and \
                              forums[row.forum_id] or forums[1],
            'title':          unescape(row.topic_title),
            'view_count':     row.topic_views,
            'post_count':     row.topic_replies + 1,
            # sticky and announce are sticky in inyoka
            'sticky':         bool(row.topic_type),
            'solved':         row.topic_fixed == 2,
            'locked':         row.topic_status == 1,
            'ubuntu_version': ubuntu_version_map.get(row.topic_version),
            'ubuntu_distro':  ubuntu_distro_map.get(row.topic_desktop),
            'author_id':      row.topic_poster,
        })
        session.commit()

    del forums

    print 'Converting posts'

    s = select([post_table, post_text_table],
               (post_table.c.post_id == post_text_table.c.post_id),
               use_labels=True)

    for row in select_blocks(s):
        text = convert_bbcode(unescape(row[post_text_table.c.post_text]),
                              row[post_text_table.c.bbcode_uid])
        session.execute(sa_post_table.insert(values={
            'id':            row[post_table.c.post_id],
            'topic_id':      row[post_table.c.topic_id],
            'author_id':     row[post_table.c.poster_id],
            'pub_date':      datetime.fromtimestamp(row[post_table.c.post_time]),
            'hidden':        False,
            'text':          text,
            'rendered_text': '',

        }))
        session.commit()

    print 'fixing forum references'

    # fix topic table
    session.execute(sa_topic_table.update(values={
        # last post id
        sa_topic_table.c.last_post_id: select(
            [func.min(sa_post_table.c.id)],
            sa_topic_table.c.id == sa_post_table.c.topic_id
        ),
        # first post id
        sa_topic_table.c.first_post_id: select(
            [func.max(sa_post_table.c.id)],
            sa_topic_table.c.id == sa_post_table.c.topic_id
        ),
        # post count
        sa_topic_table.c.post_count: select(
            [func.count(sa_post_table.c.id)],
            sa_topic_table.c.id == sa_post_table.c.topic_id
        )
    }))

    # fix forum table
    session.execute(sa_forum_table.update(values={
        # last post id
        sa_forum_table.c.last_post_id: select(
            [func.max(sa_topic_table.c.last_post_id)],
            sa_topic_table.c.forum_id == sa_forum_table.c.id
        ),
        # post count
        sa_forum_table.c.post_count: select([func.count(sa_post_table.c.id)],
            (sa_forum_table.c.id == sa_topic_table.c.forum_id) &
            (sa_topic_table.c.id == sa_post_table.c.topic_id)
        ),
        # topic count
        sa_forum_table.c.topic_count: select([func.count(sa_topic_table.c.id)],
            sa_forum_table.c.id == sa_topic_table.c.forum_id
        )
    }))

    session.commit()

    # Fix anon user:
    cur = connection.cursor()
    cur.execute("UPDATE forum_topic SET author_id = 1 WHERE author_id = -1;")
    cur.execute("UPDATE forum_post SET author_id = 1 WHERE author_id = -1;")
    connection._commit()


def convert_groups():
    engine, meta, conn = forum_db()

    group_table = Table('%sgroups' % FORUM_PREFIX, meta, autoload=True)
    relation_table = Table('%suser_group' % FORUM_PREFIX, meta, autoload=True)

    sel = select([group_table],
                 group_table.c.group_description != "Personal User")

    for group in conn.execute(sel):
        Group.objects.create(**{
                'pk':        group.group_id,
                'name':      group.group_name,
        })

    subselect = select([group_table.c.group_id],
                       group_table.c.group_description != "Personal User")
    sel_relation = select([relation_table],
                          relation_table.c.group_id.in_(subselect))

    dengine = create_engine(DJANGO_URI, echo=False, convert_unicode=True)
    dmeta = MetaData()
    dmeta.bind = dengine
    dconn = dengine.connect()
    django_user_group_rel = Table('portal_user_groups', dmeta, autoload=True)

    for erg in conn.execute(sel_relation):
        ins = django_user_group_rel.insert(values={
            'user_id':  erg.user_id,
            'group_id': erg.group_id
        })
        dconn.execute(ins)

    dconn.close()
    conn.close()


def convert_polls():
    engine, meta, conn = forum_db()

    poll_table = Table('%svote_desc' % FORUM_PREFIX, meta, autoload=True)
    poll_opt_table = Table('%svote_results' % FORUM_PREFIX, meta,
                           autoload=True)
    voter_table = Table('%svote_voters' % FORUM_PREFIX, meta, autoload=True)

    topics_with_poll = []

    for row in select_blocks(poll_table.select()):
        if row.vote_length == 0:
            end_time = None
        else:
            end_time = datetime.fromtimestamp(
                row.vote_start + row.vote_length
            )

        poll = Poll(**{
            'id':         row.vote_id,
            'question':   unescape(row.vote_text),
            'start_time': datetime.fromtimestamp(row.vote_start),
            'topic_id':   row.topic_id,
            'end_time':   end_time,
        })
        session.commit()

        topics_with_poll.append(row.topic_id)

    for row in conn.execute(poll_opt_table.select()):
        session.execute(sa_poll_option_table.insert(values={
            'poll_id': row.vote_id,
            'name':    unescape(row.vote_option_text),
            'votes':   row.vote_result
        }))
        session.commit()

    for row in conn.execute(voter_table.select()):
        try:
            session.execute(sa_poll_vote_table.insert(values={
                'voter_id': row.vote_user_id,
                'poll_id':  row.vote_id,
            }))
            session.commit()
        except OperationalError:
            # unfortunately we have corrupt data :/
            continue

    # Fixing Topic.has_poll
    session.execute(sa_topic_table.update(
            sa_topic_table.c.id.in_(topics_with_poll)
        ), has_poll=True
    )

    # Fix anon user:
    session.execute(sa_poll_vote_table.update(
            sa_poll_vote_table.c.voter_id == -1
        ), voter_id = 1
    )
    session.commit()


def convert_privileges():
    engine, meta, conn = forum_db()
    auth_table = Table('%sauth_access' % FORUM_PREFIX, meta, autoload=True)

    for row in conn.execute(auth_table.select()):
        try:
            group = Group.objects.get(pk=row.group_id)
        except Group.DoesNotExist:
            continue

        forum = Forum.query.get(int(row.forum_id))
        if forum is None:
            continue

        flags = {
            'read':        bool(row.auth_read),
            'reply':       bool(row.auth_reply),
            'create':      bool(row.auth_post),
            'edit':        bool(row.auth_edit),
            'revert':      bool(row.auth_mod),
            'delete':      bool(row.auth_delete),
            'sticky':      bool(row.auth_sticky) or \
                               bool(row.auth_announce),
            'vote':        bool(row.auth_vote),
            'create_poll': bool(row.auth_pollcreate),
            'upload':      bool(row.auth_attachments),
            'moderate':    bool(row.auth_mod)
        }
        flags = [name for name in flags.keys() if flags[name]]
        if 'moderate' in flags:
            # moderate means for phpbb that the user can do everything but
            # for inyoka it doesn't
            flags = PRIVILEGES

        Privilege(forum, **{
            'group': group,
            'bits':  join_flags(*flags),
        })
        session.commit()


def convert_topic_subscriptions():
    engine, meta, conn = forum_db()
    subscription_table = Table('%stopics_watch' % FORUM_PREFIX, meta,
                               autoload=True)

    transaction.enter_transaction_management()
    transaction.managed(True)

    # According to http://www.phpbbdoctor.com/doc_columns.php?id=22
    # we need to add both notify_status = 1|0 to out watch_list.
    for row in conn.execute(subscription_table.select()):
        try:
            Subscription.objects.create(user_id=row.user_id,
                                        topic_id=row.topic_id,
                                        notified=row.notify_status)
        # Ignore missing topics...
        except:
            pass
    transaction.commit()


def convert_forum_subscriptions():
    engine, meta, conn = forum_db()
    subscription_table = Table('%sforums_watch' % FORUM_PREFIX, meta,
                               autoload=True)

    transaction.enter_transaction_management()
    transaction.managed(True)
    for row in conn.execute(subscription_table.select()):
        try:
            Subscription.objects.create(user_id=row.user_id,
                                        forum_id=row.forum_id)
        except:
            pass
    transaction.commit()



def convert_attachments():
    engine, meta, conn = forum_db()
    attachment_desc_table = Table('%sattachments_desc' % FORUM_PREFIX, meta,
                                  autoload=True)
    attachment_table = Table('%sattachments' % FORUM_PREFIX, meta,
                             autoload=True)

    sel = select([attachment_desc_table, attachment_table.c.post_id], \
          and_(attachment_table.c.attach_id == attachment_desc_table.c.attach_id,\
          attachment_table.c.post_id != 0))

    att_dict = {}
    conn.execute('set session transaction isolation level read committed')
#    for row in select_blocks(sel):
    for row in conn.execute(sel):
        try:
	    file_ = open(path.join(OLD_ATTACHMENTS, row.physical_filename),'rb')
        except IOError:
            continue
        att = Attachment.create(row.real_filename, file_.read(), None, [],
                              id=row.attach_id, comment=unescape(row.comment),
                              post_id=row.post_id)
        att_dict.setdefault(row.post_id,[]).append(row.attach_id)
        file_.close()
        session.commit()

    cur = connection.cursor()
    cur.execute('set session transaction isolation level read committed')
    cur.execute('UPDATE forum_attachment SET post_id = null')
    connection._commit()

    for key, item in att_dict.items():
    	try:
		Attachment.update_post_ids(item, key)
	except IOError:
	        print key, item	

def convert_privmsgs():
    engine, meta, conn = forum_db()

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

        try:
            m = PrivateMessage()
            m.id = msg.privmsgs_id
            m.author_id = msg.privmsgs_from_userid;
            m.subject = unescape(msg.privmsgs_subject)
            m.pub_date = datetime.fromtimestamp(msg.privmsgs_date)
            m.text = convert_bbcode(unescape(msg_text.privmsgs_text),
                                    msg_text.privmsgs_bbcode_uid)
            m.save()
        except (IntegrityError, OperationalError, meOperationalError):
            print "skipped error"
            pass

        # If the status is sent, the first user is the sender.
        if msg.privmsgs_type in (1, 2, 4):
            user = msg.privmsgs_from_userid
            second_user = msg.privmsgs_to_userid
        # Else the Recipient is the user for the first message.
        # This only happens if the sender deletes his message.
        else:
            user = msg.privmsgs_to_userid
            second_user = msg.privmsgs_from_userid

        if m.id is not None:
            try:
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
            except (IntegrityError, OperationalError, meOperationalError):
                # and again corrupted data on database side...
                # (e.g one private message is bind to an user_id that does not exist)
                print "skipped error"
                pass

        conn.execute(msg_table.update(msg_table.c.privmsgs_id.in_(ids)), done=True)

        if i == 500:
            transaction.commit()
            i = 0
        else:
            i += 1
        connection.queries = []
    transaction.commit()


def convert_ikhaya():
    import re
    from textile import textile
    from markdown import markdown
    from xml.sax import saxutils

    def parse_imgs(text):
        def render_img(match):
            style = []
            img_style = []
            args = match.group()[2:-2].split('|')
            id = args[0]
            desc = len(args) > 1 and args[1] or None
            align = len(args) > 2 and args[2] or None
            size = len(args) > 3 and args[3] or None

            if id not in dynamic_images:
                return ''

            if align in ('left', 'right', 'center'):
                style.append('float: %s' % align)
                img_style.append('float: %s' % align)

            if size:
                if 'x' in size:
                    width, height = size.split('x')
                    style.append('width: %spx' % width)
                    img_style.extend(['width: %spx' % width, 'height: %spx' % height])

            img_code = '<img src="%s" alt="%s" style="%s" />' % (
                dynamic_images[id].get_file_url(), desc or id, ';'.join(img_style)
            )
            if desc:
                return ''.join([
                    '<div style="%s">' % ';'.join(style),
                    img_code,
                    '<br />%s' % desc,
                    '</div>'
                ])
            else:
                return img_code

        return IMG_RE.sub(render_img, text)

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
        text = parse_imgs(text)
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

    engine = create_engine(OLD_PORTAL_URI, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    category_table = Table('ikhaya_categories', meta, autoload=True)
    article_table = Table('ikhaya_entries', meta, autoload=True)
    image_table = Table('static_images', meta, autoload=True)
    user_table = Table('auth_users', meta, autoload=True)

    # contains a mapping of old_user_id -> new_user_id
    user_mapping = {}
    dynamic_images = {}
    static_images = {}
    force = {
        'tux123': 'tux21b',
        'beewee': 'highwaychile',
        'Calvin': 'Eva',
        'V_for_Vortex': 'V for Vortex',
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

    idents = []

    # we have two different icon tables in our old portal :/
    names = ['allgemein.png', 'edubuntu.png', 'gnome.png', 'kde.png', 'key.png',
        'kubuntu.png', 'kxubuntu.png', 'linux.png', 'software.png', 'ubuntu.png',
        'ubuntu_und_ich.png', 'ubuntuusers.png', 'veranstaltung.png',
        'wochenrueckblick.png', 'xubuntu.png']

    for name in names:
        f = StaticFile(**{
            'identifier':       name,
            'file':             path.join('portal', 'files', name),
            'is_ikhaya_icon':   True
        })
        f.save()
        idents.append(name)
        static_images[name] = f

    for image in select_blocks(image_table.select()):
        ident = image.image.split('/')[-1]
        while ident in idents:
            ident = ident.split('.')
            ident[-2] += '2'
            ident = '.'.join(ident)
        idents.append(ident)
        f = StaticFile(**{
            'identifier':   ident,
            'file':         image.image.replace('uploads', 'portal/files')
        })
        f.save()
        dynamic_images[image.identifer] = f

    category_mapping = {}
    for data in category_table.select().execute():
        if data.name.startswith('W'):
            import pdb
            pdb.set_trace()
        category = Category(name=fix_encoding(data.name))
        category.save()
        category_mapping[data.id] = category

    for data in article_table.select().execute():
        Article(
            pk = data.id,
            subject=fix_encoding(data.subject),
            pub_date=data.pub_date,
            author_id=user_mapping[data.author_id],
            intro=render_article(fix_encoding(data.intro), data.parser),
            text=render_article(fix_encoding(data.text), data.parser),
            public=data.public,
            category=category_mapping[data.category_id],
            is_xhtml=1,
            icon=data.icon2 and dynamic_images.get(data.icon2) or \
                static_images.get(data.icon.split('/')[-1])
        ).save()
        connection.queries = []


def convert_pastes():
    from pygments.lexers import get_all_lexers
    engine = create_engine(OLD_PORTAL_URI, convert_unicode=True)
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
    f = file('linked_pastes')
    linked = [int(id) for id in f.read().split('\n')[:-1]]
    f.close()
    for paste in select_blocks(paste_table.select()):
        if not paste.id in linked:
            continue
        lang = mapping.get(paste.language, paste.language)
        if not lang or lang not in lexers:
            lang = 'text'
        Entry(
            title=u'kein Titel',
            lang=lang,
            code=fix_encoding(paste.code),
            pub_date=paste.date,
            author=anonymous,
            id=paste.id
        ).save()
        connection.queries = []


def convert_static_pages():
    engine = create_engine(OLD_PORTAL_URI, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    page_table = Table('static_pages', meta, autoload=True)

    for page in select_blocks(page_table.select()):
        StaticPage(**{
            'key':      page.identifier,
            'title':    page.title,
            'content':  page.content.encode('iso-8859-15').decode('utf-8')
        }).save()
        connection.queries = []


MODE_MAPPING = {
        'users':         convert_users,
        'wiki':          convert_wiki,
        'ikhaya':        convert_ikhaya,
        'pastes':        convert_pastes,
        'groups':        convert_groups,
        'forum':         convert_forum,
        'topic_subscriptions': convert_topic_subscriptions,
        'forum_subscriptions': convert_forum_subscriptions,
        'privileges':    convert_privileges,
        'polls':         convert_polls,
        'attachments':   convert_attachments,
        'privmsgs':      convert_privmsgs,
        'static_pages':  convert_static_pages,
}


if __name__ == '__main__':
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
    print 'Converting groups'
    convert_groups()
    print 'Converting forum data'
    convert_forum()
    print 'Converting polls'
    convert_polls()
    print 'Converting attachments'
    convert_attachments()
    print 'Converting subscriptions'
    convert_topic_subscriptions()
    convert_forum_subscriptions()
    print 'Converting privileges'
    convert_privileges()
    print 'Converting wiki data'
    convert_wiki()
    print 'Converting ikhaya data'
    convert_ikhaya()
    print 'Converting pastes'
    convert_pastes()
    print 'Converting private messages'
    convert_privmsgs()
    print 'Converting static pages'
    convert_static_pages()
