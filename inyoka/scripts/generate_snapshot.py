#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.generate_snapshot
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Creates a snapshot of all wiki pages using docbook format.

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL.
"""
import os
import re
import shutil
from os import path
from datetime import datetime
from django.conf import settings
from inyoka.utils.urls import href
from inyoka.wiki.models import Page
from inyoka.wiki.parser import parse
from inyoka.utils.templating import jinja_env

INTERNAL_LINK_REGEX = re.compile('<ulink url="/([^"]*)')
INTERNAL_IMG_REGEX = re.compile('<imagedata fileref="%s\?target=([^"]*)' %
                                href('wiki', '_image'))


def create_snapshot(folder):
    # remove the snapshot folder and recreate it
    try:
        shutil.rmtree(folder)
    except OSError:
        pass
    os.mkdir(folder)

    # create the snapshot folder structure
    page_folder = path.join(folder, 'pages')
    attachment_folder = path.join(folder, 'attachments')
    os.mkdir(page_folder)
    os.mkdir(attachment_folder)

    tpl = jinja_env.get_template('snapshot/docbook_page.xml')
    pages = []
    for page in Page.objects.all():
        rev = page.revisions.all()[0]
        if page.trace > 1:
            # page is a subpage
            # create subdirectories
            for part in page.trace[:-1]:
                pth = path.join(rev.attachment and attachment_folder or
                                page_folder, *part.split('/'))
                if not path.exists(pth):
                    os.mkdir(pth)

        if rev.attachment:
            # page is an attachment
            shutil.copyfile(rev.attachment.filename, path.join(pth,
                            path.split(rev.attachment.filename)[1]))
        else:
            # page is a normal text page
            f = file(path.join(page_folder, '%s.xml' % page.name), 'w+')
            content = rev.text.render(format='docbook')

            # perform some replacements to make links and images work
            #: this contains a string pointing to the snapshots root directory
            content = INTERNAL_LINK_REGEX.sub(r'<ulink url="pages/\1.xml',
                                              content)
            content = INTERNAL_IMG_REGEX.sub(r'<imagedata fileref="attachments'
                                             r'/\1', content)
            f.write(tpl.render({
                'page': page,
                'content': content
            }).encode('utf-8'))
            f.close()
            pages.append(page.name)

    # create book index page
    tpl = jinja_env.get_template('snapshot/docbook_book.xml')
    f = file(path.join(folder, 'snapshot.xml'), 'w+')
    f.write(tpl.render({
        'today': datetime.utcnow(),
        'pages': pages
    }))
    f.close()


if __name__ == '__main__':
    create_snapshot('snapshot')
