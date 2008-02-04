#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.converter
    ~~~~~~~~~~~~~~~~~~~~~~~~

    This script converts all data of the old wiki, forum and portal to the new
    inyoka structure.

    :copyright: Copyright 2007 by Benjamin.
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
from inyoka.wiki.models import Page as InyokaPage
from inyoka.portal.user import User

users = {}


def convert_wiki():
    # XXX: Ignore some pages like LocalSpellingWords
    request = RequestCLI()
    for name in request.rootpage.getPageList():
        print name
        page = Page(request, name)
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

            if line.action in ('SAVE', 'SAVENEW'):
                f = file(page.get_rev(rev=int(line.rev))[0])
                kwargs['text'] = f.read().decode('utf-8')
                f.close()
                if int(rev_id) == 1:
                    new_page = InyokaPage.objects.create(name, **kwargs)
                else:
                    new_page.edit(**kwargs)
            elif line.action == 'ATTNEW':
                att = line.extra
                pth = path.join(page.getPagePath(), 'attachments', att)
                f = file(pth)
                InyokaPage.objects.create('%s/%s' % (name, att), u'',
                    attachment=f.read(), attachment_filename=att, **kwargs)
                f.close()
            elif line.action == 'ATTDEL':
                att = line.extra
                att_page = InyokaPage.objects.get('%s/%s' % (name, att))
                att_page.edit(deleted=True, **kwargs)
            else:
                raise NotImplementedError(line.action)


if __name__ == '__main__':
    print 'Converting wiki data'
    convert_wiki()
