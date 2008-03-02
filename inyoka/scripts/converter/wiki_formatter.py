# -*- coding: utf-8 -*-
"""
    inyoka.scripts.converter
    ~~~~~~~~~~~~~~~~~~~~~~~~

    This file contains a MoinMoin formatter that can be used to convert
    MoinMoin syntax to inyoka syntax.

    :copyright: Copyright 2007 by Benjamin Wiegand.
    :license: GNU GPL.
"""
import re
from MoinMoin.formatter.text_html import Formatter
from MoinMoin.formatter.base import FormatterBase
from inyoka.scripts.converter.create_templates import templates
from inyoka.wiki.utils import normalize_pagename

PAGE_TEMPLATE_NAME = 'Wiki/Vorlagen/%s'

macros = []
class InyokaFormatter(FormatterBase):
    list_depth = 0

    def macro(self, macro_obj, name, args):
        if name not in macros:
            macros.append(name)
            print name
        # TODO: Not yet handled are RandomMirror, RedirectCheck, Tasten
        if name in ['Diskussion']:
            # TODO: Do something for discussoin
            return u''

        replacements = {
            'TableOfContents': u'Inhaltsverzeichnis',
            'PageCount':       u'Seitenzahl',
            'LikePages':       u'ÄhnlicheSeiten',
            'RecentChanges':   u'LetzteÄnderungen',
            'OrphanedPages':   u'VerwaisteSeiten',
            'WantedPages':     u'FehlendeSeiten',
            'Anchor':          u'Anker'
        }

        if name in replacements:
            name = replacements[name]

        elif name == 'Anmerkung':
            return u'((%s))' % u''.join(args)

        elif name == 'Tags':
            return u'# X-Tags: ' + args

        elif name in templates.keys() or name == 'Ausbaufaehig':
            if name in ('Pakete', 'Getestet', 'InArbeit'):
                args = [a.strip() for a in args.split(',')]
            else:
                args = args and [args] or []
            args = [PAGE_TEMPLATE_NAME % name.replace('ae', u'ä')] + args
            name = 'Vorlage'

        elif name == 'Bild':
            args = [a.strip() for a in args.split(',')]
            if len(args) > 2 and args[2] in ('links', 'rechts', 'zentriert'):
                args[2] = {
                    'links': 'left',
                    'rechts': 'right',
                    'zentriert': 'center'
                }[args[2]]
                if not args[1]:
                    args.pop(1)
                    args[1] = u'align=%s' % args[1]
                    if len(args) > 2 and args[2]:
                        args[2] = u"alt='%s'" % args[2]

        elif name == 'Pakete':
            args = [a.strip() for a in args.split(',')]

        elif name == 'Include':
            args = [a.strip() for a in args.split(',')]
            name = 'Vorlage'

        elif name == 'ImageLink':
            args = [a.strip() for a in args.split(',')]
            img = args[0]
            link = args[1]
            height = u''
            width = u''

            if '/' not in img:
                img = './' + img

            for arg in args[1:]:
                if arg.startswith('alt='):
                    img += ",alt='%s'" % arg[4:]
                elif arg.startswith('width='):
                    width = args[6:]
                elif arg.startswith('height='):
                    height = args[7:]

            if width or height:
                img += u',%sx%s' % (width, height)

            img = u'[[Bild(%s)]]' % img

            if '://' in link:
                return u'[%s %s]' % (link, img)
            else:
                return u'[:%s:%s]' % (link, img)

        elif name == 'PageList':
            name = 'Seitenliste'
            args = args.strip()
            if args.startswith('regex:'):
                args = [u'pattern=%s' % args[6:]]
            else:
                args = []

        if args:
            return u'[[%s(%s)]]' % (name, ', '.join(
                ' ' in a and ("'%s'" % a) or a for a in args
            ))
        else:
            return u'[[%s]]' % name

    def processor(self, processor_name, lines, is_parser=0):
        # remove the #!name thing
        lines.pop(0)

        if processor_name == 'Text':
            result = [self.preformatted(1)]
            for line in lines:
                result.append(line + u'\n')
            result.append(self.preformatted(0))
            return u''.join(result)

        # most processors are page tempaltes in inyoka
        if processor_name != 'Wissen':
            return u'[[Vorlage(%s, \'%s\')]]' % (
                PAGE_TEMPLATE_NAME % processor_name, u'\n'.join(lines)
            )
        else:
            links = []
            for line in lines:
                for match in re.findall('\[([^\]]+)\]', line):
                    try:
                        int(match)
                    except ValueError:
                        links.append(u"'[%s]'" % match)
            return u'[[Vorlage(%s, %s)]]' % (
                PAGE_TEMPLATE_NAME % processor_name,
                u', '.join(links)
            )

    def pagelink(self, on, pagename=u'', page=None, **kw):
        pagename = normalize_pagename(pagename)
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
        return u'||'

    def table_cell(self, on, attrs=None, **kw):
        if on:
            return u'||'
        return u''

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
