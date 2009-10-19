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
import sys
import time
import shutil
from os import path
from urllib import quote
from hashlib import md5
from itertools import cycle, izip
from werkzeug import url_unquote
from inyoka.conf import settings
from inyoka.utils.urls import href
from inyoka.utils.text import escape, normalize_pagename
from inyoka.wiki.models import Page
from inyoka.wiki.acl import has_privilege
from inyoka.portal.user import User

try:
    from eventlet import coros

    # this imports a special version of the urllib2 module that uses non-blocking IO
    from eventlet.green import urllib2
except ImportError:
    print "To get better performance, install eventlet."
    coros = None
    import urllib2


FOLDER = 'static_wiki'
URL = href('wiki')
DONE_SRCS = {}

SRC_RE = re.compile(r'src="([^"]+)"')
STYLE_RE = re.compile(r'(?:rel="stylesheet"\s+type="text/css"\s+)href="([^"]+)"')
FAVICON_RE = re.compile(r'rel="shortcut icon" href="([^"]+)"')
TAB_RE = re.compile(r'(<div class="navi_tabbar navigation">).+?(</div>)', re.DOTALL)
META_RE = re.compile(r'(<p class="meta">).+?(</p>)', re.DOTALL)
NAVI_RE = re.compile(r'(<ul class="navi_global">).+?(</ul>)', re.DOTALL)
IMG_RE = re.compile(r'href="%s\?target=([^"]+)"' % href('wiki', '_image'))
LINK_RE = re.compile(r'href="%s([^"]+)"' % href('wiki'))
STARTPAGE_RE = re.compile(r'href="(%s)"' % href('wiki'))
ERROR_REPORT_RE = re.compile(r'<a href=".[^"]+" id="user_error_report_link">Fehler melden</a><br/>')
POWERED_BY_RE = re.compile(r'<li class="poweredby">.*?</li>', re.DOTALL)
SEARCH_PATHBAR_RE = re.compile(r'<form .*? class="search">.+?</form>', re.DOTALL)
DROPDOWN_RE = re.compile(r'<div class="dropdown">.+?</div>', re.DOTALL)

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


def save_file(url, is_main_page=False, is_static=False):
    if not INCLUDE_IMAGES and not is_main_page and not is_static:
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
    return os.path.join('_', DONE_SRCS[hash])


def fix_path(pth):
    return normalize_pagename(pth, False).rsplit('/', 1)[-1]


def replacer(func, parts, is_main_page):
    pre = (parts and u''.join('../' for i in xrange(parts)) or './')
    def replacer(match):
        return func(match, pre, is_main_page)
    return replacer


def handle_src(match, pre, is_main_page):
    is_static = 'static' in match.groups()[0]
    return u'src="%s%s"' % (pre, save_file(match.groups()[0], is_main_page, is_static))


def handle_img(match, pre, is_main_page):
    return u'href="%s%s"' % (pre, save_file(href('wiki', '_image', target=url_unquote(match.groups()[0].encode('utf8'))), is_main_page))


def handle_style(match, pre, is_main_page):
    ret = u'rel="stylesheet" type="text/css" href="%s%s"' % (pre, save_file(match.groups()[0], is_main_page, True))
    return ret


def handle_favicon(match, pre, is_main_page):
    ret = u'rel="shortcut icon" href="%s%s"' % (pre, save_file(match.groups()[0], is_main_page, True))
    return ret


def handle_link(match, pre, is_main_page):
    return u'href="%s%s.html"' % (pre, fix_path(match.groups()[0]))


def handle_powered_by(match, pre, is_main_page):
    return u'<li class="poweredby">Generiert mit <a href="http://ubuntuusers.de/inyoka">Inyoka</a></li>'


def handle_startpage(match, pre, is_main_page):
    return u'href="%s%s.html"' % (pre, settings.WIKI_MAIN_PAGE.lower())


REPLACERS = (
    (IMG_RE,            handle_img),
    (SRC_RE,            handle_src),
    (STYLE_RE,          handle_style),
    (FAVICON_RE,        handle_favicon),
    (LINK_RE,           handle_link),
    (STARTPAGE_RE,      handle_startpage),
    (POWERED_BY_RE,     handle_powered_by),
    (META_RE,           ''),
    (NAVI_RE,           ''),
    (ERROR_REPORT_RE,   ''),
    (GLOBAL_MESSAGE_RE, ''),
    (SEARCH_PATHBAR_RE, ''),
    (DROPDOWN_RE,       ''),
    (TAB_RE,            SNAPSHOT_MESSAGE))


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
    todo = pages - excluded_pages


    def _fetch_and_write(name):
        parts = 0
        is_main_page = False

        if not has_privilege(user, name, 'read'):
            return

        page = Page.objects.get_by_name(name, False, True)
        if page.name in excluded_pages:
            # however these are not filtered before…
            return

        if page.name == settings.WIKI_MAIN_PAGE:
            is_main_page = True

        if page.rev.attachment:
            # page is an attachment
            return
        if len(page.trace) > 1:
            # page is a subpage
            # create subdirectories
            for part in page.trace[:-1]:
                pth = path.join(FOLDER, 'files', *fix_path(part).split('/'))
                if not path.exists(pth):
                    os.mkdir(pth)
                parts += 1

        content = fetch_page(name)
        if content is None:
            return
        content = content.decode('utf8')

        for regex, repl in REPLACERS:
            if callable(repl):
                repl = replacer(repl, parts, is_main_page)
            content = regex.sub(repl, content)

        def _write_file(pth):
            with open(pth, 'w+') as fobj:
                fobj.write(content.encode('utf-8'))

        _write_file(path.join(FOLDER, 'files', '%s.html' % fix_path(page.name)))

        if is_main_page:
            content = re.compile(r'(src|href)="\./([^"]+)"') \
                    .sub(lambda m: '%s="./files/%s"' % (m.groups()[0], m.groups()[1]), content)
            _write_file(path.join(FOLDER, 'index.html'))

        time.sleep(0.5)

    if coros is None:
        # use some dummy class for the coroutine pool
        class pool(object):
            def execute(self, callback, *args):
                return callback(*args)
        pool = pool()
    else:
        # use the eventlet coroutine pool implementation
        pool = coros.CoroutinePool(max_size=10)

    waiters = []

    for percent, name in izip(percentize(len(todo)), todo):
        waiters.append(pool.execute(_fetch_and_write, name))
        pb.update(percent)

    if coros is not None:
        # only the eventlet implementation supports waiting
        for waiter in waiters:
            waiter.wait()

    print ("Created Wikisnapshot with %s pages; excluded %s pages"
           % (len(todo), len(excluded_pages)))


if __name__ == '__main__':
    create_snapshot()
