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
sys.path.append(WIKI_PATH)

from os import path
from datetime import datetime
from MoinMoin.Page import Page
from MoinMoin.request import RequestCLI
from MoinMoin.logfile import editlog
from MoinMoin.wikiutil import version2timestamp
from MoinMoin.parser.wiki import Parser
from inyoka.wiki.models import Page as InyokaPage
from inyoka.portal.user import User
from inyoka.utils.converter import InyokaFormatter
users = {}


def convert_wiki():
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


if __name__ == '__main__':
    print 'Converting wiki data'
    convert_wiki()
