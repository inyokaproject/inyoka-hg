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
import time
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
from inyoka.wiki.acl import has_privilege
from inyoka.portal.user import User

FOLDER = 'static_wiki'
URL = href('wiki')
DONE_SRCS = {}

SRC_RE = re.compile(r'src="([^"]+)"')
TAB_RE = re.compile(r'(<div class="navi_tabbar navigation">).+?(</div>)', re.DOTALL)
META_RE = re.compile(r'(<p class="meta">).+?(</p>)', re.DOTALL)
NAVI_RE = re.compile(r'(<ul class="navi_global">).+?(</ul>)', re.DOTALL)
IMG_RE = re.compile(r'href="%s\?target=([^"]+)"' % href('wiki', '_image'))
LINK_RE = re.compile(r'href="%s([^"]+)"' % href('wiki'))
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
    try:
        data = urllib2.urlopen(os.path.join(URL, quote(name.encode('utf8')))).read()
    except urllib2.HTTPError, e:
        print u"http error on page „%s”: %s" % (name, e)
        return None
    return data


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


def fix_path(pth):
    return pth.replace(' ', '_').lower()


def handle_src(match):
    return u'src="%s"' % save_file(match.groups()[0])


def handle_img(match):
    return u'href="%s"' % save_file(href('wiki', '_image', target=url_unquote(match.groups()[0].encode('utf8'))))


def handle_link(parts):
    def replacer(match):
        pre = link = (parts and u''.join('../' for i in xrange(parts)) or './')
        return u'href="%s%s.html"' % (pre, fix_path(match.groups()[0]))
    return replacer



def create_snapshot():
    # remove the snapshot folder and recreate it
    try:
        shutil.rmtree(FOLDER)
    except OSError:
        pass

    user = User.objects.get_anonymous_user()

    # create the folder structure
    os.mkdir(FOLDER)
    attachment_folder = path.join(FOLDER, '_')
    os.mkdir(attachment_folder)

    pb = ProgressBar(40)

    pages = Page.objects.get_page_list(existing_only=True)
    for percent, name in izip(percentize(len(pages)), pages):
        parts = 0

        if '/Baustelle/' in name or '/Benutzer' in name or not has_privilege(user, name, 'read'):
            continue

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
                parts += 1

        content = fetch_page(name)
        pb.update(percent)
        if content is None:
            continue
        content = content.decode('utf8')

        content = META_RE.sub('', content)
        content = NAVI_RE.sub('', content)
        content = IMG_RE.sub(handle_img, content)
        content = SRC_RE.sub(handle_src, content)
        content = LINK_RE.sub(handle_link(parts), content)
        content = TAB_RE.sub(SNAPSHOT_MESSAGE, content)

        f = file(path.join(FOLDER, '%s.html' % fix_path(page.name)), 'w+')
        f.write(content.encode('utf8'))
        f.close()
        #time.sleep(2)


if __name__ == '__main__':
    create_snapshot()
