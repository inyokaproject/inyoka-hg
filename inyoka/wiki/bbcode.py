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


    :copyright: Copyright 2007-2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import re
from inyoka.wiki.parser.transformers import DEFAULT_TRANSFORMERS
from inyoka.wiki.parser.constants import HTML_COLORS
from inyoka.wiki.parser.lexer import Lexer
from inyoka.wiki.parser import nodes

_color_re = re.compile(r'#?([a-f0-9]{3}){1,2}$')
_block_re = re.compile(r'\[(.*?)(?:\s*=\s*(".*?"|.*?))?\]')
_newline_re = re.compile(r'(?<!\n)(\n)(?!\s*\n)')
_free_link_re = re.compile('(?<!\[url\=|\[url\])(%s[^\s/]+(/[^\s.,:;?]*'
                           '([.,:;?][^\s.,:;?]+)*)?)' % Lexer._url_pattern,
                           re.IGNORECASE)

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


class Parser(object):
    """
    Parse BBCode into `nodes`.
    """

    def __init__(self, text, transformers=None):
        self.tokens = []
        self.pos = self.depth = 0
        text = u'\n'.join(text.replace('\r\n', '\n').splitlines())
        # replace free links with [url] links
        pos = 0
        result = []
        for match in _free_link_re.finditer(text):
            result.append(text[pos:match.start()])
            result.append(u'[url]%s[/url]' % text[match.start():match.end()])
            pos = match.end()
        else:
            result.append(text[pos:])
        text = u''.join(result)

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
            return nodes.Link(token.attr, self.parse_until('/url'))
        target = self.parse_until('/url', raw=True)
        return nodes.Link(target, [nodes.Text(target)])

    def parse_user(self):
        """parse [user]-tags."""
        t = self.expect_tag('user')
        if t.attr:
            return nodes.InterWikiLink('user', t.attr,
                             self.parse_until('/user'))
        user = self.parse_until('/user', raw=True)
        return nodes.InterWikiLink('user', user)

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
        children = self.parse_until('/mod')
        return nodes.Text('XXX load macro here')

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
                           self.token.name == '/mark' and
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

        children = []

        # because of phpBB's crappy syntax we treat text before the
        # first list item as list item too. phpBB simply does an
        # splitting by the [*] markers and causes broken markup because
        # of that...
        crippled = []
        is_indeed_crippled = False
        for node in self.parse_until(('*', '/list'), push_back=True):
            if not node.is_text_node or node.text.strip():
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
            item = self.parse_until(('*', '/list'), push_back=True)
            children.append(nodes.ListItem(item))
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
