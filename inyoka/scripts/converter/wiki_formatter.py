# -*- coding: utf-8 -*-
"""
    inyoka.scripts.converter.wiki_formatter
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This file contains a MoinMoin formatter that can be used to convert
    MoinMoin syntax to inyoka syntax.

    :copyright: Copyright 2007-2008 by Benjamin Wiegand, Armin Ronacher.
    :license: GNU GPL.
"""
import re
from MoinMoin.formatter.base import FormatterBase
from inyoka.scripts.converter.converter import PAGE_REPLACEMENTS
from inyoka.scripts.converter.create_templates import templates
from inyoka.wiki.utils import normalize_pagename
from MoinMoin.parser.wiki import Parser
from inyoka.forum.models import Topic

addslashes = lambda x: x.replace('"', '\\"')


# Hack to disable camel case
class InyokaParser(Parser):
    def __init__(self, raw, request, **kw):
        self.formatting_rules = re.sub(r"\(\?P<word>.*\n", "",
                                       self.formatting_rules)
        self.formatting_rules = re.sub(r"\(\?P<interwiki>.*\n", "",
                                       self.formatting_rules)
        Parser.__init__(self, raw, request, **kw)


class InyokaFormatter(FormatterBase):
    list_trace = []
    in_link = False
    link_target = None
    #: This integer determines whether paragraph() should create line breaks
    #: or not (0 means no, everything bigger than 0 means yes)
    #: Don't set it manually bug use the _paragraph_breaks() function.
    no_paragraph_breaks = 0

    def _paragraph_breaks(self, yes):
        if not yes:
            self.no_paragraph_breaks += 1
        else:
            self.no_paragraph_breaks -= 1

    def _format(self, text):
        """Format a string"""
        parser = InyokaParser(text, self.request)
        return self.request.redirectedOutput(parser.format, self)

    def macro(self, macro_obj, name, args):
        if name in ['Diskussion']:
            topic_id = int(args.split(',')[0].strip())
            if Topic.query.get(topic_id):
                self.inyoka_page.topic_id = topic_id
            return u''

        replacements = {
            'TableOfContents': u'Inhaltsverzeichnis',
            'PageCount':       u'Seitenzahl',
            'LikePages':       u'ÄhnlicheSeiten',
            'RecentChanges':   u'LetzteÄnderungen',
            'OrphanedPages':   u'VerwaisteSeiten',
            'WantedPages':     u'FehlendeSeiten',
            'Anchor':          u'Anker',
            'Include':         u'Vorlage',
            'NewPage':         u'NeueSeite',
        }

        if name in replacements:
            name = replacements[name]
            args = [a.strip() for a in (args or '').split(',')]

        elif name == 'user':
            return u'[user:%s:]' % args

        elif name == 'Anmerkung':
            return u'((%s))' % u''.join(args)

        elif name == 'Tags':
            return u'# X-Tags: ' + args

        elif name == 'MailTo':
            args = [a.strip() for a in (args or '').split(',')]
            replacements = {
                'AT': '@',
                'DOT': '.',
                'DASH': '-',
                ' ': ''
            }
            for s, r in replacements.iteritems():
                args[0] = args[0].replace(s, r)
            return u'[mailto:%s%s]' % (args[0],
                                       args[1] and u' ' + args[1] or u'')
        elif name in templates.keys() or name == 'Ausbaufaehig':
            if name in ('Pakete', 'Getestet', 'InArbeit'):
                args = [a.strip() for a in args.split(',')]
            elif name == 'Tasten':
                args = ['+'.join(a.strip() for a in args.split('+'))]
            else:
                args = args and [args] or []
            args = [name.replace('ae', u'ä')] + args
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

        if name in ['Inhaltsverzeichnis', 'Seitenzahl']:
            args = []

        if args:
            return u'[[%s(%s)]]' % (name, ', '.join(
                re.findall('[\'" ]', a)
                    and ('"%s"' % addslashes(a)) or a
                for a in args
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
        self._paragraph_breaks(False)
        if processor_name == 'Wissen':
            content = []
            content_re = re.compile('\s+\*\s+\[\d+\]:(.+)')
            for line in lines:
                match = content_re.match(line)
                if not match:
                    continue
                line = match.groups()[0].strip()
                content.append(self._format(line))
            code = u'{{{#!vorlage Wissen\n%s\n}}}' % u'\n'.join(content)
        else:
            # most processors are page templates in inyoka
            # but you can embed them via macros and parsers.
            code = u'{{{#!vorlage %s\n%s\n}}}\n' % (processor_name,
                                      self._format(u'\n'.join(lines)))
        self._paragraph_breaks(True)
        return code

    def pagelink(self, on, pagename=u'', page=None, **kw):
        if pagename in PAGE_REPLACEMENTS:
            pagename = PAGE_REPLACEMENTS[pagename]
        pagename = normalize_pagename(pagename)
        if on:
            self.in_link = True
            self.link_target = pagename
            return u'[:%s:' % (pagename)
        self.in_link = False
        self.link_target = None
        return u']'

    def interwikilink(self, on, interwiki, pagename, **kw):
        if on:
            return u'[%s:%s:' % (interwiki, pagename)
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
        if self.in_link and self.link_target == text:
            return u''
        return text

    def paragraph(self, on, **kwargs):
        FormatterBase.paragraph(self, on)
        if self.no_paragraph_breaks:
            return u''
        return u'\n'

    def bullet_list(self, on, **kw):
        if on:
            self._paragraph_breaks(False)
            self.list_trace.append('bullet')
            return u''
        else:
            self.list_trace.pop()
            self._paragraph_breaks(True)
            return u''

    def number_list(self, on, type=None, start=None, **kw):
        if on:
            self._paragraph_breaks(False)
            self.list_trace.append('number')
            return u''
        else:
            self.list_trace.pop()
            self._paragraph_breaks(True)
            return u''

    def listitem(self, on, **kwargs):
        if on:
            spaces = u' ' * len(self.list_trace)
            if self.list_trace[-1] == 'bullet':
                return u'\n%s* ' % spaces
            else:
                return u'\n%s1. ' % spaces
        return u''

    def heading(self, on, depth, **kwargs):
        if on:
            return u'%s ' % (u'=' * depth)
        return ' %s' % ('=' * depth)

    def rule(self, size=None, **kw):
        return u'----'

    def preformatted(self, on, **kwargs):
        if on:
            return u'{{{'
        return u'}}}'

    def table(self, on, attrs=None, **kw):
        if on:
            self._paragraph_breaks(False)
            return u''
        self._paragraph_breaks(True)
        return u'\n'

    def table_row(self, on, attrs=None, **kw):
        if on:
            return u'\n'
        return u'||'

    def table_cell(self, on, attrs=None, **kw):
        attr = {'rowstyle': '', 'cellstyle': '', 'tablestyle': ''}
        span = None
        if attrs:
            for k, v in attrs.iteritems():
                v = v.strip('"')
                if k.startswith('table'):
                    k = k[5:]
                    prefix = 'table'
                elif k.startswith('row'):
                    k = k[3:]
                    prefix = 'row'
                elif k.startswith('cell'):
                    k = k[4:]
                    prefix = 'cell'
                else:
                    prefix = 'cell'
                try:
                    attr[prefix + 'style'] += '%s: %s; ' % ({
                        'bgcolor': 'background-color',
                        'align': 'text-align',
                        'valign': 'vertical-align',
                        'width': 'width',
                        'height': 'height'
                    }[k], v)
                except KeyError:
                    if k == 'colspan':
                        if int(v) > 1:
                            span = '-' + v
                    elif prefix + k == 'rowspan':
                        if int(v) > 1:
                            span = '|' + v
                    elif k == 'style':
                        if not v.endswith(';'):
                            v += ';'
                        attr[prefix + 'style'] += v
                    else:
                        attr[prefix + k] = v

        attr_str = ''
        if span:
            attr_str += span
        for k, v in attr.iteritems():
            if v:
                attr_str += ' %s="%s"' % (k, v.strip())
        if on:
            return u'||%s' % (attr_str and ('<%s>' % attr_str.strip()) or '')
        return u''

    def linebreak(self, preformatted=1):
        if preformatted:
            return u'\\\n'
        return u'\n'

    def code(self, on, **kw):
        return u'``'

    def strike(self, on, **kw):
        if on:
            return u'--('
        return u')--'

    def attachment_link(self, url, text, **kw):
        return u'[attachment:%s/%s:%s]' % (self.page.page_name, url, text)

    def attachment_image(self, url, **kw):
        return u'[[Bild(%s/%s)]]' % (self.page.page_name, url)

    def definition_list(self, on, **kw):
        if on:
            self._paragraph_breaks(False)
            return u''
        self._paragraph_breaks(True)
        return u'\n'

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

    def comment(self, text):
        text = text.replace('#', '')
        if text.strip().startswith('acl'):
            return u''
        if text.strip().startswith('redirect'):
            try:
                page = normalize_pagename(' '.join(text.split(' ')[1:]))
                return u'# X-Redirect: %s\n' % page
            except (IndexError, ValueError):
                return u''
        return u'##%s\n' % text
