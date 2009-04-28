#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.generate_static_wiki
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Creates a snapshot of all wiki pages in HTML format.

    :copyright: 2008 by Benjamin Wiegand
                2009 by Christopher Grebs.
    :license: GNU GPL, see LICENSE for more details..
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
from inyoka.conf import settings
from inyoka.utils.urls import href
from inyoka.wiki.models import Page
from inyoka.wiki.acl import has_privilege
from inyoka.portal.user import User

FOLDER = '/nfs/www/de/static_wiki'
URL = href('wiki')
DONE_SRCS = {}

SRC_RE = re.compile(r'src="([^"]+)"')
STYLE_RE = re.compile(r'rel="stylesheet" type="text/css" href="([^"]+)"')
FAVICON_RE = re.compile(r'rel="shortcut icon" href="([^"]+)"')
TAB_RE = re.compile(r'(<div class="navi_tabbar navigation">).+?(</div>)', re.DOTALL)
META_RE = re.compile(r'(<p class="meta">).+?(</p>)', re.DOTALL)
NAVI_RE = re.compile(r'(<ul class="navi_global">).+?(</ul>)', re.DOTALL)
IMG_RE = re.compile(r'href="%s\?target=([^"]+)"' % href('wiki', '_image'))
LINK_RE = re.compile(r'href="%s([^"]+)"' % href('wiki'))
STARTPAGE_RE = re.compile(r'href="(%s)"' % href('wiki'))
ERROR_REPORT_RE = re.compile(r'<a href=".[^"]+" id="user_error_report_link">Fehler melden</a><br/>')

GLOBAL_MESSAGE_RE = re.compile(r'(<div class="message global">).+?(</div>)', re.DOTALL)

SNAPSHOT_MESSAGE = u'''<div class="message staticwikinote">
<strong>Hinweis:</strong> Dies ist nur ein statischer Snapshot unseres Wikis.  Dieser kann nicht bearbeitet werden und veraltet sein.  Das richtige Wiki ist unter <a href="%s">wiki.ubuntuusers.de</a> zu finden.
</div>''' % URL

EXCLUDE_PAGES = [u'Benutzer/', u'Anwendertreffen/', u'Baustelle/', u'LocoTeam/',
                 u'Wiki/Vorlagen', u'Vorlage/', u'Verwaltung/', u'Galerie', 'Trash/',
                 u'Messen/', u'UWN-Team/']
# we're case insensitive
EXCLUDE_PAGES = [x.lower() for x in EXCLUDE_PAGES]


INCLUDE_IMAGES = False

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


def save_file(url, is_main_page=False):
    if not INCLUDE_IMAGES and not is_main_page:
        return ""
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
        f = file(os.path.join(FOLDER, 'files', '_', fname), 'wb+')
        f.write(content)
        f.close()
        DONE_SRCS[hash] = fname
    return os.path.join('./_', DONE_SRCS[hash])


def fix_path(pth):
    return pth.replace(' ', '_').lower()


def replacer(func, parts, is_main_page):
    pre = (parts and u''.join('../' for i in xrange(parts)) or './')
    def replacer(match):
        return func(match, pre, is_main_page)
    return replacer


def handle_src(match, pre, is_main_page):
    return u'src="%s%s"' % (pre, save_file(match.groups()[0], is_main_page))


def handle_img(match, pre, is_main_page):
    return u'href="%s%s"' % (pre, save_file(href('wiki', '_image', target=url_unquote(match.groups()[0].encode('utf8'))), is_main_page))


def handle_style(match, pre, is_main_page):
    return u'href="%s%s"' % (pre, save_file(match.groups()[0], is_main_page))


def handle_link(match, pre, is_main_page):
    return u'href="%s%s.html"' % (pre, fix_path(match.groups()[0]))


def startpage_link(match, pre, is_main_page):
    return u'href="%s%s.html"' % (pre, settings.WIKI_MAIN_PAGE.lower())


def create_snapshot():
    # remove the snapshot folder and recreate it
    try:
        shutil.rmtree(FOLDER)
    except OSError:
        pass

    user = User.objects.get_anonymous_user()

    # create the folder structure
    os.mkdir(FOLDER)
    os.mkdir(path.join(FOLDER, 'files'))
    attachment_folder = path.join(FOLDER, 'files', '_')
    os.mkdir(attachment_folder)

    pb = ProgressBar(40)

    unsorted = Page.objects.get_page_list(existing_only=True)
    pages = set()
    excluded_pages = set()
    # sort out excluded pages
    for page in unsorted:
        for exclude in EXCLUDE_PAGES:
            if exclude in page.lower():
                excluded_pages.add(page)
            else:
                pages.add(page)
    pages = pages - excluded_pages


    for percent, name in izip(percentize(len(pages)), pages):
        is_main_page = False
        parts = 0

        if not has_privilege(user, name, 'read'):
            continue

        page = Page.objects.get_by_name(name, False, True)
        if page.name in excluded_pages:
            # however these are not filtered before…
            continue

        if page.name == settings.WIKI_MAIN_PAGE:
            is_main_page = True

        if page.rev.attachment:
            # page is an attachment
            continue
        if len(page.trace) > 1:
            # page is a subpage
            # create subdirectories
            for part in page.trace[:-1]:
                pth = path.join(FOLDER, 'files', *fix_path(part).split('/'))
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
        content = ERROR_REPORT_RE.sub('', content)
        content = GLOBAL_MESSAGE_RE.sub('', content)
        content = IMG_RE.sub(replacer(handle_img, parts, is_main_page), content)
        content = SRC_RE.sub(replacer(handle_src, parts, is_main_page), content)
        content = LINK_RE.sub(replacer(handle_link, parts, is_main_page), content)
        content = STARTPAGE_RE.sub(replacer(startpage_link, parts, is_main_page), content)
        content = STYLE_RE.sub(replacer(handle_style, parts, is_main_page), content)
        content = FAVICON_RE.sub(replacer(handle_style, parts, is_main_page), content)
        content = TAB_RE.sub(SNAPSHOT_MESSAGE, content)

        f = file(path.join(FOLDER, 'files', '%s.html' % fix_path(page.name)), 'w+')
        f.write(content.encode('utf8'))
        f.close()
        time.sleep(.2)
    os.chdir(FOLDER)
    #XXX: this needs to be done another way... for now I replaced all links
    #     by hand. I don't like the idea of using re here as well... --entequak
    #os.link('./files/%s.html' % settings.WIKI_MAIN_PAGE.lower(),
    #        '%s.html' % settings.WIKI_MAIN_PAGE.lower())


if __name__ == '__main__':
    create_snapshot()
