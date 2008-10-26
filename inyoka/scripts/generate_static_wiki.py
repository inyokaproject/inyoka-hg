#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.generate_static_wiki
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Creates a snapshot of all wiki pages in HTML format.

    :copyright: 2008 by Benjamin Wiegand.
    :license: GNU GPL.
"""
import os
import re
import shutil
import urllib2
from os import path
from md5 import md5
from urllib import quote
from datetime import datetime
from werkzeug import url_unquote
from inyoka.utils.urls import href
from inyoka.wiki.models import Page

FOLDER = 'static_wiki'
URL = href('wiki')
DONE_SRCS = {}

SRC_RE = re.compile(r'src="([^"]+)"')
TAB_RE = re.compile(r'(<div class="navi_tabbar navigation">).+?(</div>)', re.DOTALL)
META_RE = re.compile(r'(<p class="meta">).+?(</p>)', re.DOTALL)
NAVI_RE = re.compile(r'(<ul class="navi_global">).+?(</ul>)', re.DOTALL)
IMG_RE = re.compile(r'href="%s\?target=([^"]+)"' % href('wiki', '_image'))
LINK_RE = re.compile(r'href="%s' % href('wiki'))


def fetch_page(name):
    return urllib2.urlopen(os.path.join(URL, quote(name.encode('utf8')))).read()


def save_file(url):
    if url.startswith('/'):
        url = os.path.join(URL, url[1:])
    hash = md5(url).hexdigest()
    if hash not in DONE_SRCS:
        try:
            u = urllib2.urlopen(url)
            ext = u.headers.subtype
            content = u.read()
        except:
            ext = content = ''
        fname = '%s.%s' % (hash, ext)
        f = file(os.path.join(FOLDER, '_', fname), 'wb+')
        f.write(content)
        f.close()
        DONE_SRCS[hash] = fname
    return os.path.join('/_', DONE_SRCS[hash])


def handle_src(match):
    return u'src="%s"' % save_file(match.groups()[0])


def handle_img(match):
    return u'href="%s"' % save_file(href('wiki', '_image', target=url_unquote(match.groups()[0].encode('utf8'))))


def fix_path(pth):
    return pth.replace(' ', '_').lower()


def create_snapshot():
    # remove the snapshot folder and recreate it
    try:
        shutil.rmtree(FOLDER)
    except OSError:
        pass

    # create the folder structure
    os.mkdir(FOLDER)
    attachment_folder = path.join(FOLDER, '_')
    os.mkdir(attachment_folder)

    pages = []
    for name in Page.objects.get_page_list(existing_only=True):
        page = Page.objects.get(name=name)
        rev = page.revisions.all()[0]
        if rev.attachment:
            # page is an attachment
            continue
        if len(page.trace) > 1:
            # page is a subpage
            # create subdirectories
            for part in page.trace[:-1]:
                pth = path.join(FOLDER, *fix_path(part).split('/'))
                if not path.exists(pth):
                    os.mkdir(pth)

        f = file(path.join(FOLDER, '%s.html' % fix_path(page.name)), 'w+')
        try:
            content = fetch_page(name).decode('utf8')
        except:
            continue

        content = TAB_RE.sub(u'''<div class="message">
<strong>Hinweis:</strong> Da unsere Server überlastet sind, haben wir das Wiki auf eine statische Version umgestellt; es kann deswegen zur Zeit nicht bearbeitet werden.
</div>''', content)
        content = META_RE.sub('', content)
        content = NAVI_RE.sub('', content)
        content = IMG_RE.sub(handle_img, content)
        content = SRC_RE.sub(handle_src, content)
        content = LINK_RE.sub('href="/', content)
        f.write(content.encode('utf8'))
        f.close()
        pages.append(page.name)


if __name__ == '__main__':
    create_snapshot()
