#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.converter
    ~~~~~~~~~~~~~~~~~~~~~~~~

    This script converts all data of the old wiki, forum and portal to the new
    inyoka structure.

    :copyright: Copyright 2007 by Benjamin Wiegand.
    :license: GNU GPL.
"""
import sys

WIKI_PATH = '/srv/www/de/wiki'
FORUM_URI = 'mysql://root:@127.0.0.1/ubuntuusers?charset=utf8'
FORUM_PREFIX = 'ubuntu_'
AVATAR_PREFIX = '/path/'
sys.path.append(WIKI_PATH)

from os import path
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
    #for name in ['Archiv/Apple Powerbook G4 Titanium']:
        print name
        # XXX: add filter
        if 'Hardwaredatenbank' in name or 'Spelling' in name or 'Anwendetreffen' in name:
            continue
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

def convert_forum():
    from sqlalchemy import create_engine, MetaData, Table
    from sqlalchemy.sql import select
    from _mysql_exceptions import IntegrityError
    from inyoka.wiki import bbcode
    # Clear the users table
    #User.objects.all().delete()
    engine = create_engine(FORUM_URI, echo=False, convert_unicode=True)
    meta = MetaData()
    meta.bind = engine
    conn = engine.connect()
    users_table = Table('%susers' % FORUM_PREFIX, meta, autoload=True)
    odd_coordinates = []
    mail_error = []
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
        #TODO: Everthing gets truncated, dunno if this is the correct way.
        # This might break the layout...
        data = {
            'pk': row.user_id,
            'username': row.username[:30],
            'email': row.user_email[:50] or None,
            'password': '!',
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
            'signature': bbcode.parse(row.user_sig).to_markup(),
            #TODO: coordinates
            'coordinates_long': co_long,
            'coordinates_lat': co_lat,
            'location': row.user_from[:200],
            #'gpgkey': '',
            'occupation': bbcode.parse(row.user_occ).to_markup()[:200],
            'interests': bbcode.parse(row.user_interests).to_markup()[:200],
            'website': row.user_website[:200],
            #'_settings' : '',
            #TODO: 'is_manager': 0,
            #TODO:
            #'forum_last_read'
            #'forum_read_status'
            #'forum_welcome'
        }
        try:
            User.objects.create(**data)
        except IntegrityError, e:
            # same email adress, forbidden
            if e.args[1].endswith('key 3'):
                data['email'] = "(%d)%s" % (row.user_id ,data['email'])
                User.objects.create(**data)
                mail_error.append(row.user_id)
            else:
                print e
                sys.exit(1)
    print odd_coordinates, mail_error

if __name__ == '__main__':
    print 'Converting wiki data'
    convert_wiki()
    print 'Converting forum data'
    convert_forum()
