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
import urllib2
import urlparse
from os import path
from datetime import datetime
from inyoka.utils.urls import href
from inyoka.wiki.models import Page
from inyoka.utils.templating import jinja_env

NESTED1 = re.compile('<ulink url="([^"]*)"><mediaobject><imageobject><imagedata')
NESTED2 = re.compile('/></imageobject></mediaobject></ulink>')
INTERNAL_IMG_REGEX = re.compile('<imagedata fileref="%s\?target=([^"]*)' %
                                href('wiki', '_image'))
THUMBNAIL_REGEX = re.compile('<imagedata fileref="%s\?([^"]*)"' %
                             href('wiki', '_image'))


def handle_thumbnail(m):
    d = {}
    for s in m.groups()[0].split('&'):
        k, v = s.split('=')
        d[k] = v
    r = u'<imagedata fileref="../attachments/%s"' % urllib2.unquote(d['target'])
    if 'width' in d:
        r += u' width="%s"' % d['width']
    if 'height' in d:
        r += u' height="%s"' % d['height']
    return r


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
    for page in Page.objects.all():
        if not (page.name == 'Startseite' or page.name.startswith('Wiki')):
            continue
        rev = page.revisions.all()[0]
        if page.trace > 1:
            # page is a subpage
            # create subdirectories
            for part in page.trace[:-1]:
                pth = path.join(rev.attachment and attachment_folder or
                                page_folder, *part.split('/')).replace(' ', '_')
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
            content = INTERNAL_IMG_REGEX.sub(r'<imagedata fileref="../attachments'
                                             r'/\1', content)
            content = THUMBNAIL_REGEX.sub(handle_thumbnail, content)
            # XXX: Images inside links don't work, this fixes this
            f.write(tpl.render({
                'page': page,
                'content': content
            }).encode('utf-8'))
            f.close()


if __name__ == '__main__':
    create_snapshot('snapshot')
