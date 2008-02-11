# -*- coding: utf-8 -*-
"""
    inyoka.scripts.converter
    ~~~~~~~~~~~~~~~~~~~~~~~~

    This file contains a MoinMoin formatter that can be used to convert
    MoinMoin syntax to inyoka syntax.

    :copyright: Copyright 2007 by Benjamin Wiegand.
    :license: GNU GPL.
"""
from MoinMoin.formatter.text_html import Formatter
from MoinMoin.formatter.base import FormatterBase


class InyokaFormatter(FormatterBase):
    list_depth = 0

    # don't execute dynamic stuff
    def macro(self, macro_obj, name, args):
        if args:
            return u'[[%s(%s)]]' % (name, args)
        else:
            return u'[[%s]]' % name

    def processor(self, processor_name, lines, is_parser=0):
        result = [self.preformatted(1)]
        for line in lines:
            result.append(line + u'\n')
        result.append(self.preformatted(0))
        return ''.join(result)

    def pagelink(self, on, pagename=u'', page=None, **kw):
        if on:
            return u'[:%s:' % (pagename)
        return u']'

    def interwikilink(self, on, interwiki, pagename, **kw):
        if on:
            return u'[:%s:%s:' % (interwiki, pagename)
        return u']'

    def url(self, on, url=None, **kw):
        if on:
            return u'[%s ' % url
        return u']'

    def strong(self, on):
        return u"'''"

    def emphasis(self, on):
        return u"''"

    def underline(self, on):
        return u'__'

    def _text(self, text):
        return text

    def text(self, text):
        return text

    def paragraph(self, on, **kwargs):
        return u''

    def bullet_list(self, on, **kw):
        self.list_type = 'bullet'
        if on:
            self.list_depth += 1
        else:
            self.list_depth -= 1
        return u'\n'

    def number_list(self, on, type=None, start=None, **kw):
        self.list_type = 'number'
        if on:
            self.list_depth += 1
        else:
            self.list_depth -= 1
        return u'\n'

    def listitem(self, on, **kwargs):
        if on:
            spaces = u' ' * self.list_depth
            if self.list_type == 'bullet':
                return u'%s* ' % spaces
            else:
                return u'%s1. ' % spaces
        return u'\n'

    def heading(self, on, depth, **kwargs):
        if on:
            return u'\n%s ' % (u'=' * depth)
        return ' %s\n' % ('=' * depth)

    def rule(self, size=None, **kw):
        return u'\n----\n'

    def preformatted(self, on, **kwargs):
        if on:
            return u'\n{{{'
        return u'}}}\n'

    def table(self, on, attrs=None, **kw):
        if not on:
            return u'\n'
        return u''

    def table_row(self, on, attrs=None, **kw):
        if on:
            return u'\n'
        return u''

    def table_cell(self, on, attrs=None, **kw):
        return u'||'

    def linebreak(self, preformatted=1):
        if preformatted:
            return u'\n\n'
        return u'\n'

    def code(self, on, **kw):
        return u'``'

    def strike(self, on, **kw):
        if on:
            return u'--('
        return u')--'

    def attachment_link(self, url, text, **kw):
        # TODO: Implement something like [attachment:asd.tar.gz:asd] that
        #       links directly to the attachment and not on the attachment
        #       wiki page
        return u'[:%s/%s:%s]' % (self.page.page_name, url, text)

    def attachment_image(self, url, **kw):
        # TODO
        return u''

    def definition_list(self, on, **kw):
        if not on:
            return u'\n'
        return u''

    def definition_term(self, on, **kw):
        if on:
            return u'\n '
        return u':: '

    def definition_desc(self, on, **kw):
        if not on:
            return u'\n'
        return u''

    def small(self, on, **kw):
        if on:
            return u'~-'
        return u'-~'

    def big(self, on, **kw):
        if on:
            return u'~+'
        return u'+~'

    def sup(self, on, **kw):
        return u'^^'

    def sub(self, on, **kw):
        return u',,'
