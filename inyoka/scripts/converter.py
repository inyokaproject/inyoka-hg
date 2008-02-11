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
FORUM_URI = 'mysql://%s:%s@%s/ubuntuusers_old?charset=utf8' % (settings.DATABASE_USER,
    settings.DATABASE_PASSWORD, settings.DATABASE_HOST)
FORUM_PREFIX = 'ubuntu_'
AVATAR_PREFIX = '/path/'
sys.path.append(WIKI_PATH)

from os import path
from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.sql import select
from datetime import datetime
from inyoka.wiki.models import Page as InyokaPage
from inyoka.portal.user import User
users = {}


def convert_wiki():
    from MoinMoin.Page import Page
    from MoinMoin.request import RequestCLI
    from MoinMoin.logfile import editlog
    from MoinMoin.wikiutil import version2timestamp
    from MoinMoin.parser.wiki import Parser
    from inyoka.utils.converter import InyokaFormatter
    # XXX: Ignore some pages like LocalSpellingWords
    request = RequestCLI()
    formatter = InyokaFormatter(request)
    request.formatter = formatter
    new_page = None
    for name in request.rootpage.getPageList():
    #for name in ['Analog-TV']:
        if 'Hardwaredatenbank' in name or 'Spelling' in name or 'Anwendertreffen' in name or 'Benutzer/' in name or 'Analog-TV' in name or name == 'Kate':
            continue
        print name
        page = Page(request, name, formatter=formatter)
        request.page = page
        for line in editlog.EditLog(request, rootpagename=name):
            rev_id = line.rev
            kwargs = {
                'note': line.comment,
                'change_date': datetime.fromtimestamp(version2timestamp(
                                                     line.ed_time_usecs))
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
    # TODO: select none.....
    s = select([users_table])
    result = conn.execute(s)
    for row in result:
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
                    ':%s]' % row.user_sig_bbcode_uid,']')
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
            'avatar': avatar[:100],
            'icq': row.user_icq[:16],
            'msn': row.user_msnm[:200],
            'aim': row.user_aim[:200],
            'yim': row.user_yim[:200],
            'jabber': row.user_jabber[:200],
            'signature': signature,
            #TODO: coordinates
            'coordinates_long': co_long,
            'coordinates_lat': co_lat,
            'location': row.user_from[:200],
            #'gpgkey': '',
            'occupation': row.user_occ[:200],
            'interests': row.user_interests[:200],
            'website': row.user_website[:200],
            #'_settings' : '',
            #TODO: 'is_manager': 0,
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
    #print odd_coordinates, mail_error


def convert_forum():
    from inyoka.forum.models import Forum, Topic
    from sqlalchemy import create_engine, MetaData, Table
    from sqlalchemy.sql import select

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
        6: 'kubuntu' # KDE(4) is stille kubuntu ;)
    }

    result = conn.execute(s)

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
            'first_post_id': row.topic_first_post_id,
            'last_post_id': row.topic_last_post_id,
        }
        # To work around the overwritten objects.create method...
        t = Topic(**data)
        t.save()

    conn.close()


def convert_ikhaya():
    import re
    from textile import textile
    from markdown import markdown
    from xml.sax import saxutils
    from inyoka.ikhaya.models import Article, Category, Comment

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
            return textile(text)
        if parser == 'autobr':
            return linebreaks(text)
        if parser == 'xhtml':
            return text
        return saxutils.escape(text)

    engine = create_engine('mysql://root@localhost/ubuntu_de_portal')
    meta = MetaData()
    meta.bind = engine
    category_table = Table('ikhaya_categories', meta, autoload=True)
    article_table = Table('ikhaya_entries', meta, autoload=True)
    comment_table = Table('ikhaya_comments', meta, autoload=True)
    icon_table = Table('ikhaya_icons', meta, autoload=True)

    category_mapping = {}

    for data in category_table.select().execute():
        category = Category(name=data.name)
        category.save()
        category_mapping[data.id] = category

    for data in article_table.select().execute():
        article = Article(
            subject=data.subject,
            pub_date=data.pub_date,
            intro=data.intro,
            text=render_article(data.text),
            public=data.public,
            category=category_mapping[data.category_id]
        )
        article.save()


if __name__ == '__main__':
    print 'Converting users'
    #convert_users()
    print 'Converting ikhaya data'
    #convert_ikhaya()
    print 'Converting wiki data'
    #convert_wiki()
    print 'Converting forum data'
    convert_forum()
