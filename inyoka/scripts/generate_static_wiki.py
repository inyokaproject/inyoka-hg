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
import sys
import shutil
import urllib2
from os import path
from md5 import md5
from urllib import quote
from datetime import datetime
from itertools import cycle, izip
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
SNAPSHOT_MESSAGE = u'''<div class="message">
<strong>Hinweis:</strong> Dies ist nur ein statischer Snapshot unseres Wikis.  Dieser kann weder bearbeitet werden noch kann dieser veraltet sein.  Das richtige Wiki ist unter <a href="%s">wiki.ubuntuusers.de</a> zu finden.
</div>''' % URL

# original from Jochen Kupperschmidt with some modifications
class ProgressBar(object):
    """Visualize a status bar on the console."""

    def __init__(self, max_width):
        """Prepare the visualization."""
        self.max_width = max_width
        self.spin = cycle(r'-\|/').next
        self.tpl = '%-' + str(max_width) + 's ] %c %5.1f%%'
        show(' [ ')
        self.last_output_length = 0

    def update(self, percent):
        """Update the visualization."""
        # Remove last state.
        show('\b' * self.last_output_length)

        # Generate new state.
        width = int(percent / 100.0 * self.max_width)
        output = self.tpl % ('-' * width, self.spin(), percent)

        # Show the new state and store its length.
        show(output)
        self.last_output_length = len(output)


def show(string):
    """Show a string instantly on STDOUT."""
    sys.stdout.write(string)
    sys.stdout.flush()


def percentize(steps):
    """Generate percental values."""
    for i in range(steps + 1):
        yield i * 100.0 / steps


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

    pb = ProgressBar(40)

    pages = Page.objects.get_page_list(existing_only=True)
    for percent, name in izip(percentize(len(pages)), pages):
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
        pb.update(percent)

        content = TAB_RE.sub(SNAPSHOT_MESSAGE, content)
        content = META_RE.sub('', content)
        content = NAVI_RE.sub('', content)
        content = IMG_RE.sub(handle_img, content)
        content = SRC_RE.sub(handle_src, content)
        content = LINK_RE.sub('href="/', content)
        f.write(content.encode('utf8'))
        f.close()


if __name__ == '__main__':
    create_snapshot()
