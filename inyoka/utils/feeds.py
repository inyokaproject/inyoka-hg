# -*- coding: utf-8 -*-
"""
    inyoka.utils.feeds
    ~~~~~~~~~~~~~~~~~~~

    utils for creating an atom feed.

    :copyright: 2007 by Marian Sigler.
    :license: GNU GPL, see LICENSE for more details.
"""
from django.http import HttpResponse
from django.utils.html import escape


def _make_text_block(name, content, content_type=None):
    if content_type == 'xhtml':
        return u'<%s type="xhtml">%s</%s>\n' % (
            name,
            content,
            name,
        )
    if not content_type:
        return u'<%s>%s</%s>\n' % (
            name,
            escape(content),
            name,
        )
    return u'<%s type="%s">%s</%s>\n' % (
        name,
        content_type,
        escape(content),
        name,
    )


class FeedBuilder(object):
    """
    A helper class that creates ATOM feeds.
    """
    #TODO: add test if id is unique

    def __init__(self, title=None, entries=None, **kwargs):
        """
        Create an atom feed.

        :Parameters:
          title
            the title of the feed.  Required.
          title_type
            the type attribute for the title element.  One of html, text,
            xhtml.  Default is text.
          url
            the url for the feed.
          id
            a globally unique id for the feed.  Must be an URI.  If not present
            the URL is used, but one of both is required.
          updated
            the time the feed was modified the last time.  Must be a
            `datetime.datetime` object.  If not present the latest entry's
            `updated` is used.
          feed_url
            the url to the feed.  Should be the URL that was requested.
          author
            the author of the feed.  Must be either a string (the name) or a
            dict with name (required) and uri or email (both optional).  Can be
            a list of (may be mixed, too) strings and dicts, too, if there are
            multiple authors.  Required if not every entry has an author
            element.
          icon
            an icon for the feed.
          logo
            a logo for the feed.
          rights
            copyright information for the feed.
          rights_type
            the type attribute for the rights element.  One of html, text,
            xhtml.  Default is text.
          subtitle
            a short description of the feed.
          subtitle_type
            the type attribute for the subtitle element.  One of html, text,
            xhtml.  Default is text.
          links
            additional links.  Must be a list of dictionaries with href
            (required)  and rel, type, hreflang, title, length (all optional)
          entries
            a list with the entries for the feed.  Entries can also be added
            later with add().

        For more information on the elements see
        http://www.atomenabled.org/developers/syndication/

        Everywhere where a list is demanded, any iterable can be used.
        """
        self.title = title
        self.title_type = kwargs.get('title_type')
        self.url = kwargs.get('url')
        self.id_ = kwargs.get('id', self.url)
        self.updated = kwargs.get('updated')
        self.feed_url = kwargs.get('feed_url')
        self.author = kwargs.get('author', ())
        self.icon = kwargs.get('icon')
        self.logo = kwargs.get('logo')
        self.rights = kwargs.get('rights')
        self.rights_type = kwargs.get('rights_type')
        self.subtitle = kwargs.get('subtitle')
        self.subtitle_type = kwargs.get('subtitle_type')
        self.links = kwargs.get('links', [])
        self.entries = entries and list(entries) or []

        if not hasattr(self.author, '__iter__') \
           or isinstance(self.author, (basestring, dict)):
            self.author = [self.author]
        for i, author in enumerate(self.author):
            if not isinstance(author, dict):
                self.author[i] = {'name': author}

        if not self.title:
            raise ValueError('title is required')
        if not self.id_:
            raise ValueError('id is required')
        for author in self.author:
            if 'name' not in author:
                raise TypeError('author must contain at least a name')

    def add(self, *args, **kwargs):
        '''add a new entry to the feed'''
        if len(args) == 1 and not kwargs and isinstance(args[0], FeedEntry):
            self.entries.append(args[0])
        else:
            self.entries.append(FeedEntry(*args, **kwargs))

    def __repr__(self):
        return '<%s %r (%d entries)>' % (
            self.__class__.__name__,
            self.title,
            len(self.entries)
        )

    def stream_atom(self):
        # atom demands either an author element in every entry or a global one
        if not self.author:
            if False in map(lambda e: bool(e.author), self.entries):
                self.author = ({'name': u'unbekannter Autor'},)

        if not self.updated and self.entries:
            self.updated = sorted([entry.updated for entry in
                                   self.entries])[-1]

        yield u'<?xml version="1.0" encoding="utf-8"?>\n'
        yield u'<feed xmlns="http://www.w3.org/2005/Atom">\n'
        yield '  ' + _make_text_block('title', self.title, self.title_type)
        yield u'  <id>%s</id>\n' % escape(self.id_)
        if self.entries:
            yield u'  <updated>%s</updated>\n' % \
                (self.updated.strftime('%Y-%m-%dT%H:%M:%S') + \
                (self.updated.strftime('%z') or 'Z'))
        if self.url:
            yield u'  <link href="%s" />\n' % escape(self.url)
        if self.feed_url:
            yield u'  <link href="%s" rel="self" />\n' % escape(self.feed_url)
        for link in self.links:
            yield u'  <link %s/>\n' % ''.join('%s="%s" ' % \
                (escape(k), escape(link[k])) for k in link)
        for author in self.author:
            yield u'  <author>\n'
            yield u'    <name>%s</name>\n' % escape(author['name'])
            if 'uri' in author:
                yield u'    <uri>%s</uri>\n' % escape(author['uri'])
            if 'email' in author:
                yield '    <email>%s</email>\n' % escape(author['email'])
            yield '  </author>\n'
        if self.subtitle:
            yield '  ' + _make_text_block('subtitle', self.subtitle,
                                          self.subtitle_type)
        if self.icon:
            yield u'  <icon>%s</icon>\n' % escape(self.icon)
        if self.logo:
            yield u'  <logo>%s</logo>\n' % escape(self.logo)
        if self.rights:
            yield '  ' + _make_text_block('rights', self.rights,
                                          self.rights_type)
        for entry in self.entries:
            yield u'\n'
            yield u'  <entry>\n'
            for line in entry.stream_atom():
                yield '    ' + line
            yield u'  </entry>\n'
        yield u'\n</feed>\n'

    def to_atom(self):
        return u''.join(self.stream_atom())

    def get_atom_response(self):
        content_type='application/atom+xml; charset=utf-8'
        return HttpResponse(self.to_atom(), content_type=content_type)


class FeedEntry(object):
    """
    Represents a single entry in a feed.
    """

    def __init__(self, title=None, content=None, **kwargs):
        """
        Holds an atom feed entry.

        :Parameters:
          title
            the title of the entry.  Required.
          title_type
            the type attribute for the title element.  One of html, text,
            xhtml.  Default is text.
          content
            the content of the entry.
          content_type
            the type attribute for the content element.  One of html, text,
            xhtml.  Default is text.
          summary
            a summary of the entry's content.
          summary_type
            a type attribute for the summary element.  One of html, text,
            xhtml.  Default is text.
          url
            the url for the entry.
          id
            a globally unique id for the entry.  Must be an URI.  If not present
            the URL is used, but one of both is required.
          updated
            the time the entry was modified the last time.  Must be a
            `datetime.datetime` object.  Required.
          author
            the author of the entry.  Must be either a string (the name) or a
            dict with name (required) and uri or email (both optional).  Can
            be a list of (may be mixed, too) strings and dicts, too, if there
            are multiple authors.  Required if there is no author for the
            feed.
          published
            the time the entry was initially published.  Must be a
            datetime.datetime object.
          rights
            copyright information for the entry.
          rights_type
            the type attribute for the rights element.  One of html, text,
            xhtml.  Default is text.
          links
            additional links.  Must be a list of dictionaries with href
            (required) and rel, type, hreflang, title, length (all optional)

        For more information on the elements see
        http://www.atomenabled.org/developers/syndication/

        Everywhere where a list is demanded, any iterable can be used.
        """
        self.title = title
        self.title_type = kwargs.get('title_type', 'html')
        self.content = content
        self.content_type = kwargs.get('content_type', 'html')
        self.url = kwargs.get('url')
        self.id_ = kwargs.get('id', self.url)
        self.updated = kwargs.get('updated')
        self.summary = kwargs.get('summary')
        self.summary_type = kwargs.get('summary_type', 'html')
        self.author = kwargs.get('author')
        self.published = kwargs.get('published')
        self.rights = kwargs.get('rights')
        self.links = kwargs.get('links', [])

        if not hasattr(self.author, '__iter__') \
           or isinstance(self.author, (basestring, dict)):
            self.author = [self.author]
        for i, author in enumerate(self.author):
            if not isinstance(author, dict):
                self.author[i] = {'name': author}

        if not self.title:
            raise ValueError('title is required')
        if not self.id_:
            raise ValueError('id is required')
        if not self.updated:
            raise ValueError('updated is required')
        for author in self.author:
            if 'name' not in author:
                raise TypeError('author must contain at least a name')

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.title
        )

    def stream_atom(self):
        yield _make_text_block('title', self.title, self.title_type)
        yield u'<id>%s</id>\n' % escape(self.id_)
        yield u'<updated>%s</updated>\n' % \
            (self.updated.strftime('%Y-%m-%dT%H:%M:%S') + \
            (self.updated.strftime('%z') or 'Z'))
        if self.published:
            yield u'<published>%s</published>\n' % \
                (self.published.strftime('%Y-%m-%dT%H:%M:%S') + \
                (self.published.strftime('%z') or 'Z'))
        if self.url:
            yield u'<link href="%s" />\n' % escape(self.url)
        for author in self.author:
            yield u'<author>\n'
            yield u'  <name>%s</name>\n' % escape(author['name'])
            if 'uri' in author:
                yield u'  <uri>%s</uri>\n' % escape(author['uri'])
            if 'email' in author:
                yield u'  <email>%s</email>\n' % escape(author['email'])
            yield u'</author>\n'
        for link in self.links:
            yield u'<link %s/>\n' % ''.join('%s="%s" ' % \
                (escape(k), escape(link[k])) for k in link)
        if self.summary:
            yield _make_text_block('summary', self.summary, self.summary_type)
        if self.content:
            yield _make_text_block('content', self.content, self.content_type)

    def to_atom(self):
        return u''.join(self.stream_atom())
