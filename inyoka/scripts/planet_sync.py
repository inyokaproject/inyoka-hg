#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.planet_sync
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    The ``sync`` function should be called periodically to check for new
    articles.  It checks whether the last syncronization of a blog is more
    than ``PLANET_SYNC_TIME`` ago and updates them.

    It'd be ideal if ``sync`` was called every 30 minutes.


    :copyright: 2007 by Benjamin Wiegand, Marian Sigler, Armin Ronacher.
    :license: GNU GPL, see LICENSE for more details.
"""
import re
import sys
import feedparser
import _mysql_exceptions
from time import time
from datetime import datetime
from inyoka.conf import settings
from inyoka.utils.html import escape, cleanup_html
from inyoka.planet.models import Blog, Entry


HTML_MIMETYPES = set(['text/html', 'application/xml+xhtml', 'application/xhtml+xml'])
_par_re = re.compile(r'\n{2,}')


def nl2p(s):
    """Add paragraphs to a text."""
    return u'\n'.join(u'<p>%s</p>' % p for p in _par_re.split(s))


def debug(msg):
    """Helper function that prints to stderr if debugging is enabled."""
    if settings.DEBUG:
        sys.stderr.write(msg + '\n')


def sync():
    """
    Performs a synchronization.  Articles that are already syncronized aren't
    touched anymore.
    """
    debug('debugging enabled')
    for blog in Blog.objects.filter(active=True):
        debug('syncing blog %s' % blog.name)

        # parse the feed. feedparser.parse will never given an exception
        # but the bozo bit might be defined.
        feed = feedparser.parse(blog.feed_url)
        blog_author = feed.get('author') or blog.name
        blog_author_detail = feed.get('author_detail')

        for entry in feed.entries:
            # get the guid. either the id if specified, otherwise the link.
            # if none is available we skip the entry.
            guid = entry.get('id') or entry.get('link')
            if not guid:
                debug(' no guid found, skipping')
                continue

            try:
                old_entry = Entry.objects.get(guid=guid)
            except Entry.DoesNotExist:
                old_entry = None

            # get title, url and text. skip if no title or no text is
            # given. if the link is missing we use the blog link.
            if 'title_detail' in entry:
                title = entry.title_detail.get('value') or ''
                if entry.title_detail.get('type') in HTML_MIMETYPES:
                    title = cleanup_html(title, id_prefix='entry-title-%x' %
                                         int(time()), output_format='xhtml')
                else:
                    title = escape(title)
            title = entry.get('title')
            url = entry.get('link') or blog.blog_url
            text = 'content' in entry and entry.content[0] or \
                   entry.get('summary_detail')

            if not title or not text:
                debug(' no text or title for %r found, skipping' % guid)
                continue

            # if we have an html text we use that, otherwise we HTML
            # escape the text and use that one. We also handle XHTML
            # with our tag soup parser for the moment.
            if text.get('type') in HTML_MIMETYPES:
                text = cleanup_html(text.get('value') or '',
                                    id_prefix='entry-text-%x' % int(time()),
                                    output_format='xhtml')
            else:
                text = escape(nl2p(text.get('value') or ''))

            # get the pub date and updated date. This is rather complex
            # because different feeds do different stuff
            pub_date = entry.get('published_parsed') or \
                       entry.get('created_parsed') or \
                       entry.get('date_parsed')
            updated = entry.get('updated_parsed') or pub_date
            pub_date = pub_date or updated

            # if we don't have a pub_date we skip.
            if not pub_date:
                debug(' no pub_date for %r found, skipping' % guid)
                continue

            # convert the time tuples to datetime objects.
            pub_date = datetime(*pub_date[:6])
            updated = datetime(*updated[:6])

            # get the blog author or fall back to blog default.
            author = entry.get('author') or blog_author
            author_detail = entry.get('author_detail') or blog_author_detail
            if not author and author_detail:
                author = author_detail.get('name')
            if not author:
                debug(' no author for entry %r found, skipping' % guid)
            author_homepage = author_detail and author_detail.get('href') \
                              or blog.blog_url

            # create a new entry object based on the data collected or
            # update the old one.
            entry = old_entry or Entry()
            for n in ('blog', 'guid', 'title', 'url', 'text', 'pub_date',
                      'updated', 'author', 'author_homepage'):
                setattr(entry, n, locals()[n])
                # prevent mysql warnings
                try:
                    max_length = entry._meta.get_field(n).max_length
                except AttributeError:
                    max_length = None
                if isinstance(locals()[n], basestring):
                    setattr(entry, n, locals()[n][:max_length])
            entry.save()
            debug(' synced entry %r' % guid)
        blog.last_sync = datetime.utcnow()
        blog.save()


if __name__ == '__main__':
    sync()
