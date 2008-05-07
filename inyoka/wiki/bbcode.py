# -*- coding: utf-8 -*-
"""
    inyoka.wiki.bbcode
    ~~~~~~~~~~~~~~~~~~

    This mdoule implements an ubunutuusers-phpBB compatible BBCode-Parser
    that generates `nodes`.  Because of a completely different implementation
    this parser does not use the `parsertools`.

    To get a tree of `nodes` from a bbcode text use this snippet:

    >>> from inyoka.wiki import bbcode
    >>> doc = bbcode.parse('...')


    :copyright: Copyright 2007-2008 by Armin Ronacher, Benjamin Wiegand.
    :license: GNU GPL.
"""
import re
from inyoka.wiki.parser.transformers import DEFAULT_TRANSFORMERS
from inyoka.wiki.parser.constants import HTML_COLORS
from inyoka.wiki.parser.lexer import Lexer
from inyoka.wiki.parser import nodes
from inyoka.wiki.parser.machine import MarkupWriter

_color_re = re.compile(r'#?([a-f0-9]{3}){1,2}$')
_block_re = re.compile(r'\[(.*?)(?:\s*=\s*(".*?"|.*?))?\]')
_newline_re = re.compile(r'(?<!\n)(\n)(?!\s*\n)')
_url_tags = ('url', 'img')
_url_tag_re = '|'.join('\[%s\=|\[%s\]' % (tag, tag) for tag in _url_tags)
_free_link_re = re.compile('(?<!%s)(%s[^\s/]+(/[^\s.,:;?]*([.,:;?][^\s.,:;?]'
                           '+)*)?)' % (_url_tag_re, Lexer._url_pattern),
                           re.IGNORECASE)


class BBMarkupWriter(MarkupWriter):
    def escape(self, text):
        return text


def parse(text):
    """BBCode-Parse a text."""
    return Parser(text).parse()


class Token(object):
    __slots__ = ()
    type = None


class TagToken(Token):
    __slots__ = ('raw', 'name', 'attr')
    type = intern('tag')

    def __init__(self, raw, name, attr):
        self.raw = raw
        self.name = name
        self.attr = attr

    def __unicode__(self):
        return self.raw


class TextToken(Token):
    __slots__ = ('value',)
    type = intern('text')

    def __init__(self, value):
        self.value = value

    def __unicode__(self):
        return self.value


class NewlineToken(Token):
    type = intern('newline')

    def __unicode__(self):
        return '\n'


def _make_interwiki_link(old, new=None):
    """
    Returns a parser function that converts the phpbb tag [old]page[/old]
    to an inyoka interwiki link [new:page:].
    """
    new = new and new or old
    def do(self):
        t = self.expect_tag(old)
        if t.attr:
            return nodes.InterWikiLink(new, t.attr,
                             self.parse_until('/%s' % old))
        page = self.parse_until('/%s' % old, raw=True)
        return nodes.InterWikiLink(new, page)
    return do


def _add_default_scheme(url):
    """This adds 'http://' to a string if it has no scheme"""
    if '://' not in url:
        url = u'http://%s' % url
    return url


class Parser(object):
    """
    Parse BBCode into `nodes`.
    """

    def __init__(self, text, transformers=None):
        self.tokens = []
        self.pos = self.depth = 0
        text = u'\n'.join(text.replace('\r\n', '\n').splitlines())

        if transformers is None:
            transformers = DEFAULT_TRANSFORMERS
        self.transformers = transformers

        self.handlers = {
            'b':            self.parse_strong,
            'i':            self.parse_emphasized,
            'u':            self.parse_underline,
            'url':          self.parse_url,
            'wiki':         self.parse_wiki,
            'mod':          self.parse_mod,
            'color':        self.parse_color,
            'font':         self.parse_font,
            'size':         self.parse_size,
            'mark':         self.parse_mark,
            'quote':        self.parse_quote,
            'code':         self.parse_code,
            'list':         self.parse_list,
            'img':          self.parse_img,
            'user':         self.parse_user,
            'search':       self.parse_search,
            'ikhaya':       self.parse_ikhaya,
            'wikipedia':    self.parse_wikipedia,
            'ikhaya':       self.parse_ikhaya,
            'wikipedia-en': self.parse_wikipedia_en,
            'bookzilla':    self.parse_bookzilla,
            'ubuntuwiki':   self.parse_ubuntuwiki,
            'flag':         self.parse_flag,
        }

        def add_text(value):
            for line in _newline_re.split(value):
                if line == '\n':
                    add(NewlineToken())
                elif line:
                    add(TextToken(line))

        pos = 0
        add = self.tokens.append
        for match in _block_re.finditer(text):
            start = match.start()
            if start > pos:
                add_text(text[pos:start])
            name, attr = match.groups()
            if attr and attr[:1] == attr[-1:] == '"':
                attr = attr[1:-1]
            add(TagToken(match.group(0), name.lower(), attr))
            pos = match.end()
        if pos < len(text):
            add_text(text[pos:])

    def __iter__(self):
        return self

    @property
    def token(self):
        """The current token."""
        return self.tokens[self.pos]

    @property
    def eos(self):
        """Are we at the end of the stream?"""
        return self.pos >= len(self.tokens)

    def expect_tag(self, name):
        """Expect a tag with a given name (and maybe attributes)."""
        t = self.token
        assert t.type == 'tag' and name == name
        self.next()
        return t

    def parse_until(self, name, raw=False, push_back=False):
        """Parse until a tag without attr and that name is found."""
        if isinstance(name, basestring):
            name = (name,)
        children = []
        try:
            while not self.eos and not (self.token.type == 'tag' and
                                        self.token.name in name and
                                        not self.token.attr):
                if raw:
                    children.append(unicode(self.token))
                    self.next()
                else:
                    children.append(self.parse_node())
            if not push_back:
                self.next()
        except StopIteration:
            pass
        if raw:
            return u''.join(children)
        return children

    def next(self):
        """Go one token ahead and return the old one."""
        self.pos += 1
        try:
            return self.tokens[self.pos - 1]
        except IndexError:
            raise StopIteration()

    def parse_node(self):
        """Parsing dispatcher."""
        self.depth += 1
        try:
            if self.token.type == 'text':
                val = self.token.value
                self.next()
                return nodes.Text(val)
            elif self.token.type == 'newline':
                self.next()
                return nodes.Newline()
            elif self.depth < 180 and self.token.type == 'tag' and \
                 self.token.name in self.handlers:
                return self.handlers[self.token.name]()
            else:
                val = unicode(self.token)
                self.next()
                return nodes.Text(val)
        finally:
            self.depth -= 1

    def parse_flag(self):
        """parse [flag]-tags"""
        self.expect_tag('flag')
        return nodes.Element(children=[nodes.Text(u'{')] +
                self.parse_until('/flag') + [nodes.Text(u'}')])

    def parse_strong(self):
        """parse [b]-tags"""
        self.expect_tag('b')
        return nodes.Strong(self.parse_until('/b'))

    def parse_emphasized(self):
        """parse [i]-tags"""
        self.expect_tag('i')
        return nodes.Emphasized(self.parse_until('/i'))

    def parse_underline(self):
        """parse [u]-tags"""
        self.expect_tag('u')
        return nodes.Underline(self.parse_until('/u'))

    def parse_url(self):
        """parse [url]-tags."""
        token = self.expect_tag('url')
        if token.attr:
            return nodes.Link(_add_default_scheme(token.attr),
                              self.parse_until('/url'))
        target = self.parse_until('/url', raw=True)
        return nodes.Link(_add_default_scheme(target), [nodes.Text(target)])

    def parse_wiki(self):
        """parse [wiki]-tags."""
        token = self.expect_tag('wiki')
        if token.attr:
            return nodes.InternalLink(token.attr, self.parse_until('/wiki'))
        target = self.parse_until('/wiki', raw=True)
        return nodes.InternalLink(target, [nodes.Text(target)])

    def parse_mod(self):
        """parse [mod]-tags."""
        token = self.expect_tag('mod')
        if not token.attr:
            return nodes.Text(unicode(token))
        return nodes.Moderated(token.attr, self.parse_until('/mod'))

    def parse_mark(self):
        """
        Parse [mark]-tags.  Because of popular request these are not still
        supported like before.
        """
        self.expect_tag('mark')
        return nodes.Highlighted(self.parse_until('/mark'))

    def parse_color(self):
        """parse [color]-tags"""
        t = self.expect_tag('color')
        if t.attr in HTML_COLORS:
            color = HTML_COLORS[t.attr]
        elif not t.attr or not _color_re.match(t.attr):
            return nodes.Text(unicode(t))
        else:
            color = t.attr.lstrip('#')
            if len(color) == 3:
                color = ''.join(x + x for x in color)
            color = '#' + color
        return nodes.Color(color, self.parse_until('/color'))

    def parse_font(self):
        """parse [font]-tags"""
        t = self.expect_tag('font')
        if not t.attr:
            return nodes.Text(unicode(t))
        return nodes.Font([t.attr], self.parse_until('/font'))

    def parse_size(self):
        """parse [size]-tags"""
        t = self.expect_tag('size')
        try:
            size = int(t.attr)
            if size > 30:
                raise ValueError()
        except (ValueError, TypeError):
            return nodes.Text(unicode(t))
        return nodes.Size(size, self.parse_until('/size'))

    def parse_quote(self):
        """parse [quote]-tags"""
        token = self.expect_tag('quote')
        quote = nodes.Quote(self.parse_until('/quote'))
        if not token.attr:
            return quote
        return nodes.Element([
            nodes.Text(u'%s hat geschrieben:' % token.attr),
            quote
        ])

    def parse_code(self):
        """parse [code]-tags"""
        token = self.expect_tag('code')
        children = []
        textbuf = []

        def flush():
            data = u''.join(textbuf)
            if data:
                children.append(nodes.Text(data))
            del textbuf[:]
            if not self.eos:
                self.next()

        while not self.eos and not (self.token.type == 'tag' and
                                    self.token.name == '/code' and
                                    not self.token.attr):
            if self.token.type == 'tag' and \
               self.token.name == 'mark':
                flush()
                markbuf = []
                while not (self.token.type == 'tag' and
                           self.token.name in ('/mark', '/code') and
                           not self.token.attr):
                    markbuf.append(unicode(self.token))
                    self.next()
                data = u''.join(markbuf)
                children.append(nodes.Highlighted([nodes.Text(data)]))
            else:
                textbuf.append(unicode(self.token))
            self.next()
        flush()
        return nodes.Preformatted(children)

    def parse_list(self):
        """
        Parse [list]-tags.

        Due to the fact that phpBB has a badly implemented parser we have to
        cope with some invalid markup here.  The definition of a list is not
        clear in phpBB and the markup allows some crazy things like using
        lists as pseudo indents because <ul>'s automatically indent due to a
        left margin.  We do not support invalid HTML markup (lists *must*
        have list items as children) so we add support for those pseudo items
        by making them a list item.
        """
        t = self.expect_tag('list')
        if not t.attr:
            list_type = 'unordered'
        else:
            list_type = {
                '1':        'arabic',
                'a':        'alphalower',
                'A':        'alphalower',
                '*':        'unordered'
            }.get(t.attr)
        if list_type is None:
            # ... yes. that's what phpbb does
            return nodes.Text(unicode(t))

        def is_list_end():
            return (
                self.token.type == 'tag' and
                self.token.name == '/list' and
                not self.token.attr
            )

        def finish():
            return nodes.List(list_type, children)

        def is_empty_node(node):
            return node.is_linebreak_node or \
                    (node.is_text_node and not node.text.strip())

        children = []

        # because of phpBB's crappy syntax we treat text before the
        # first list item as list item too. phpBB simply does an
        # splitting by the [*] markers and causes broken markup because
        # of that...
        crippled = []
        is_indeed_crippled = False

        for node in self.parse_until(('*', '/list'), push_back=True):
            if not is_empty_node(node):
                is_indeed_crippled = True
            crippled.append(node)

        if is_indeed_crippled:
            children.append(nodes.ListItem(crippled))
        # b0rked markup, no end tags
        if self.eos:
            return finish()

        # end of list, probably just a cripple. return
        if is_list_end():
            self.next()
            return finish()

        # oh. something unexpected. get the hell out of that loop
        if self.token.type != 'tag' or self.token.name != '*' \
           or self.token.attr:
            return finish()

        # now parse the normal list items
        self.next()
        while 1:
            items = self.parse_until(('*', '/list'), push_back=True)
            if not filter(lambda n: not is_empty_node(n), items):
                # empty list item
                continue
            children.append(nodes.ListItem(items))
            if self.eos:
                break
            elif is_list_end():
                self.next()
                break
            self.next()

        return finish()

    def parse_img(self):
        """parse [img]-tags"""
        t = self.expect_tag('img')
        src = self.parse_until('/img', raw=True)
        return nodes.Image(src, t.attr or '')

    def parse(self):
        """
        Parse everything and apply transformers.
        """
        children = []
        while not self.eos:
            children.append(self.parse_node())
        result = nodes.Document(children)
        for transformer in self.transformers:
            result = transformer.transform(result)
        return result

    parse_user = _make_interwiki_link('user')
    parse_search = _make_interwiki_link('search')
    parse_paste = _make_interwiki_link('paste')
    parse_wikipedia = _make_interwiki_link('wikipedia')
    parse_ikhaya = _make_interwiki_link('ikhaya')
    parse_wikipedia_en = _make_interwiki_link('wikipedia-en',
                                              'wikipedia_en')
    parse_bookzilla = _make_interwiki_link('bookzilla', 'isbn')
    parse_ubuntuwiki = _make_interwiki_link('ubuntuwiki', 'ubuntu')
