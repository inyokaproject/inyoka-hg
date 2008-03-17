# -*- coding: utf-8 -*-
"""
    inyoka.wiki.macros
    ~~~~~~~~~~~~~~~~~~

    The module contains the core macros and the logic to find macros.

    The term macro is derived from the MoinMoin wiki engine which refers to
    macros as small pieces of dynamic snippets that are exanded at rendering
    time.  For inyoka macros are pretty much the same just they are always
    expanded at parsing time.  However, for the sake of dynamics macros can
    mark themselves as runtime macros.  In that case during parsing the macro
    is inserted directly into the parsing as as block (or inline, depending on
    the macro settings) node and called once the data is loaded from the
    serialized instructions.

    This leads to the limitation that macros must be pickleable.  So if you
    feel the urge of creating a closure or something similar in your macro
    initializer remember that and move the code into the render method.

    For example macro implementations have a look at this module's sourcecode
    which implements all the builtin macros.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from datetime import datetime, date
from inyoka.conf import settings
from inyoka.utils.urls import href, url_encode
from inyoka.wiki.parser import nodes
from inyoka.wiki.utils import simple_filter, get_title, normalize_pagename, \
     pagename_join, is_external_target, debug_repr, dump_argstring, \
     ArgumentCollector
from inyoka.wiki.models import Page, Revision
from inyoka.utils.text import human_number
from inyoka.utils.urls import url_encode, is_http_link
from inyoka.utils.dates import parse_iso8601, format_datetime, format_time, \
     natural_date
from inyoka.utils.urls import url_for
from inyoka.utils.pagination import Pagination


def get_macro(name, args, kwargs):
    """
    Instanciate a new macro or return `None` if it doesn't exist.  This is
    used by the parser when it encounters a `macro_begin` token.  Usually
    there is no need to call this function from outside the parser.  There
    may however be macros that want to extend the functionallity of an
    already existing macro.
    """
    cls = ALL_MACROS.get(name)
    if cls is None:
        return
    return cls(args, kwargs)


class Macro(object):
    """
    Baseclass for macros.  All macros should extend from that or implement
    the same attributes.  The preferred way however is subclassing.
    """

    __metaclass__ = ArgumentCollector

    #: if a macro is static this has to be true.
    is_static = False

    #: true if this macro returns a block level node in dynamic
    #: rendering. This does not affect static rendering.
    is_block_tag = False

    #: unused in `Macro` but not `TreeMacro`.
    is_tree_processor = False

    #: set this to True if you want to do the argument parsing yourself.
    has_argument_parser = False

    #: if a macro is dynamic it's unable to emit metadata normally. This
    #: slot allows one to store a list of nodes that are sent to the
    #: stream before the macro itself is emited and removed from the
    #: macro right afterwards so that it consumes less storage pickled.
    metadata = None

    #: the arguments this macro expects
    arguments = ()

    __repr__ = debug_repr

    @property
    def macro_name(self):
        """The name of the macro."""
        return REVERSE_MACROS.get(self.__class__)

    @property
    def argument_string(self):
        """The argument string."""
        return dump_argstring(self.argument_def)

    @property
    def wiki_representation(self):
        """The macro in wiki markup."""
        args = self.argument_string
        return u'[[%s%s]]' % (
            self.macro_name,
            args and (u'(%s)' % args) or ''
        )

    def render(self, context, format):
        """Dispatch to the correct render method."""
        rv = self.build_node(context, format)
        if isinstance(rv, basestring):
            return rv
        return rv.render(context, format)

    def build_node(self, context=None, format=None):
        """
        If this is a static macro this method has to return a node.  If it's
        a runtime node a context and format parameter is passed.

        A static macro has to return a node, runtime macros can either have
        a look at the passed format and return a string for that format or
        return a normal node which is then rendered into that format.
        """


class TreeMacro(Macro):
    """
    Special macro that is processed after the whole tree was created.  This
    is useful for a `TableOfContents` macro that has to look for headline
    tags etc.

    If a macro is a tree processor the `build_node` function is passed a
    tree as only argument.  That being said it's impossible to use a tree
    macro as runtime macro.
    """

    is_tree_processor = True
    is_static = True

    #: When the macro should be expanded. Possible values are:
    #:
    #: `final`
    #:      the macro is expanded at the end of the transforming process.
    #:
    #: `initial`
    #:      the macro is expanded at the end of the parsing process, before
    #:      the transformers and other tree macro levels (default).
    #:
    #: `late`
    #:      Like initial, but after initial macros.
    stage = 'initial'

    def render(self, context, format):
        """A tree macro is not a runtime macro.  Never static"""
        raise RuntimeError('tree macro is not allowed to be non static')

    def build_node(self, tree):
        """
        Works like a normal `build_node` function but it's passed a node that
        represents the syntax tree.  It can be queried using the query
        interface attached to nodes.

        The return value must be a node, even if the macro shouldn't output
        anything.  In that situation it's recommended to return just an empty
        `nodes.Text`.
        """


class RecentChanges(Macro):
    """
    Show a table of the recent changes.  This macro does only work for HTML
    so far, all other formats just get an empty text back.
    """

    arguments = (
        ('per_page', int, 50),
    )
    is_block_tag = True

    def __init__(self, per_page):
        self.per_page = per_page

    def build_node(self, context, format):
        if not context.request or not context.wiki_page:
            return nodes.Paragraph([
                nodes.Text(u'Letzte Änderungen können von hier aus '
                           u'nicht dargestellt werden.')
            ])

        try:
            page_num = int(context.request.GET['page'])
        except (ValueError, KeyError):
            page_num = 1

        days = []
        days_found = set()

        def link_func(page_num, parameters):
            if page_num == 1:
                parameters.pop('page', None)
            else:
                parameters['page'] = str(page_num)
            rv = href('wiki', context.wiki_page)
            if parameters:
                rv += '?' + url_encode(parameters)
            return rv
        pagination = Pagination(context.request, Revision.objects.
                                select_related(depth=1), page_num,
                                self.per_page, link_func)

        for revision in pagination.objects:
            d = revision.change_date
            key = (d.year, d.month, d.day)
            if key not in days_found:
                days.append((date(*key), []))
                days_found.add(key)
            days[-1][1].append(revision)

        table = nodes.Table(class_='recent_changes')
        for day, revisions in days:
            table.children.append(nodes.TableRow([
                nodes.TableHeader([
                    nodes.Text(natural_date(day))
                ], colspan=4)
            ]))

            for rev in revisions:
                if rev.user:
                    author = nodes.Link(url_for(rev.user), [
                             nodes.Text(rev.user.username)])
                else:
                    author = nodes.Text(rev.remote_addr)
                table.children.append(nodes.TableRow([
                    nodes.TableCell([
                        nodes.Text(format_time(rev.change_date))
                    ], class_='timestamp'),
                    nodes.TableCell([
                        nodes.InternalLink(rev.page.name)
                    ], class_='page'),
                    nodes.TableCell([author], class_='author'),
                    nodes.TableCell([
                        nodes.Text(rev.note or u'')
                    ], class_='note')
                ]))

        # if rendering to html we add a pagination, pagination is stupid for
        # docbook and other static representations ;)
        if format == 'html':
            return u'<div class="recent_changes">%s%s</div>' % (
                table.render(context, format),
                '<div class="pagination">%s<div style="clear: both">'
                '<div></div>' % pagination.generate()
            )

        return table


class TableOfContents(TreeMacro):
    """
    Show a table of contents.  We do not embedd the TOC in a DIV so far and
    there is also no title on it.
    """
    stage = 'final'
    is_block_tag = True
    arguments = (
        ('max_depth', int, 3),
        ('type', {
            'unordered':    'unordered',
            'arabic0':      'arabiczero',
            'arabic':       'arabic',
            'alphabeth':    'alphalower',
            'ALPHABETH':    'alphaupper',
            'roman':        'romanlower',
            'ROMAN':        'romanupper'
        }, 'arabic')
    )

    def __init__(self, depth, list_type):
        self.depth = depth
        self.list_type = list_type

    def build_node(self, tree):
        result = nodes.List(self.list_type, class_='toc')
        stack = [result]
        for headline in tree.query.by_type(nodes.Headline):
            if headline.level > self.depth:
                continue
            elif headline.level > len(stack):
                for x in xrange(headline.level - len(stack)):
                    node = nodes.List(self.list_type)
                    if stack[-1].children:
                        stack[-1].children[-1].children.append(node)
                    else:
                        result.children.append(nodes.ListItem([node]))
                    stack.append(node)
            elif headline.level < len(stack):
                for x in xrange(len(stack) - headline.level):
                    stack.pop()
            caption = [nodes.Text(headline.text)]
            link = nodes.Link('#' + headline.id, caption)
            stack[-1].children.append(nodes.ListItem([link]))
        return result


class PageCount(Macro):
    """
    Return the number of existing pages.
    """

    def build_node(self, context, format):
        return nodes.Text(unicode(Page.objects.get_page_count()))


class PageList(Macro):
    """
    Return a list of pages.
    """

    is_block_tag = True
    arguments = (
        ('pattern', unicode, ''),
        ('case_sensitive', bool, True),
        ('shorten_title', bool, False)
    )

    def __init__(self, pattern, case_sensitive, shorten_title):
        self.pattern = pattern
        self.case_sensitive = case_sensitive
        self.shorten_title = shorten_title

    def build_node(self, context, format):
        result = nodes.List('unordered')
        pagelist = Page.objects.get_page_list()
        if self.pattern:
            pagelist = simple_filter(self.pattern, pagelist,
                                     self.case_sensitive)
        for page in pagelist:
            title = [nodes.Text(get_title(page, not self.shorten_title))]
            link = nodes.InternalLink(page, title, force_existing=True)
            result.children.append(nodes.ListItem([link]))
        return result


class AttachmentList(Macro):
    """
    Return a list of attachments or attachments below
    a given page.
    """

    is_block_tag = True
    arguments = (
        ('page', unicode, ''),
    )

    def __init__(self, page):
        self.page = page

    def build_node(self, context, format):
        result = nodes.List('unordered')
        pagelist = Page.objects.get_attachment_list(self.page or None)
        for page in pagelist:
            title = [nodes.Text(get_title(page, not self.shorten_title))]
            link = nodes.InternalLink(page, title, force_existing=True)
            result.children.append(nodes.ListItem([link]))
        return result


class OrphanedPages(Macro):
    """
    Return a list of orphaned pages.
    """

    is_block_tag = True

    def build_node(self, context, format):
        result = nodes.List('unordered')
        for page in Page.objects.get_orphans():
            title = [nodes.Text(get_title(page, True))]
            link = nodes.InternalLink(page, title,
                                      force_existing=True)
            result.children.append(nodes.ListItem([link]))
        return result


class MissingPages(Macro):
    """
    Return a list of missing pages.
    """

    is_block_tag = True

    def build_node(self, context, format):
        result = nodes.List('unordered')
        for page in Page.objects.get_missing():
            title = [nodes.Text(get_title(page, True))]
            link = nodes.InternalLink(page, title,
                                      force_existing=True)
            result.children.append(nodes.ListItem([link]))
        return result


class RedirectPages(Macro):
    """
    Return a list of pages that redirect to somewhere.
    """

    is_block_tag = True

    def build_node(self, context, format):
        result = nodes.List('unordered')
        for page in Page.objects.find_by_metadata('weiterleitung'):
            target = page.metadata.get('weiterleitung')
            link = nodes.InternalLink(page.name, [nodes.Text(page.title)],
                                      force_existing=True)
            title = [nodes.Text(get_title(target, True))]
            target = nodes.InternalLink(target, title)
            result.children.append(nodes.ListItem([link, nodes.Text(u' \u2794 '),
                                                   target]))
        return result


class PageName(Macro):
    """
    Return the name of the current page if the render context
    knows about that.  This is only useful when rendered from
    a wiki page.
    """

    def build_node(self, context, format):
        if context.wiki_page:
            return nodes.Text(context.wiki_page.name)
        return nodes.Text('Unbekannte Seite')


class NewPage(Macro):
    """
    Show a small form to create a new page below a page or in
    top level and with a given template.
    """

    is_static = True
    arguments = (
        ('base', unicode, ''),
        ('template', unicode,''),
        ('text', unicode, '')
    )

    def __init__(self, base, template, text):
        self.base = base
        self.template = template
        self.text = text

    def build_node(self):
        return nodes.html_partial('wiki/_new_page_macro.html', True,
            text=self.text,
            base=self.base,
            template=self.template
        )


class SimilarPages(Macro):
    """
    Show a list of pages similar to the page name given or the
    page from the render context.
    """

    is_block_tag = True
    arguments = (
        ('page', unicode, ''),
    )

    def __init__(self, page_name):
        self.page_name = page_name

    def build_node(self, context, format):
        if context.wiki_page:
            name = context.wiki_page
            ignore = name
        else:
            name = self.page_name
            ignore = None
        if not name:
            return nodes.error_box('Parameter Fehler', u'Du musst eine '
                                   u'Seite angeben, wenn das Makro '
                                   u'außerhalb des Wikis verwendet wird.')
        result = nodes.List('unordered')
        for page in Page.objects.get_similar(name):
            if page == ignore:
                continue
            title = [nodes.Text(get_title(page, True))]
            link = nodes.InternalLink(page, title,
                                      force_existing=True)
            result.children.append(nodes.ListItem([link]))
        return result


class TagCloud(Macro):
    """
    Show a tag cloud (or a tag list if the ?tag parameter is defined in
    the URL).
    """

    is_block_tag = True
    arguments = (
        ('max', int, 100),
    )

    def __init__(self, max):
        self.max = max

    def build_node(self, context, format):
        if context.request:
            active_tag = context.request.GET.get('tag')
            if active_tag:
                return TagList(active_tag, _raw=True). \
                       build_node(context, format)
        container = nodes.Layer(class_='tagcloud')
        for tag in Page.objects.get_tagcloud(self.max):
            if tag['count'] == 1:
                title = 'eine Seite'
            else:
                title = '%s Seiten' % human_number(tag['count'], 'feminine')
            container.children.extend((
                nodes.Link('?' + url_encode({
                        'tag':  tag['name']
                    }), [nodes.Text(tag['name'])],
                    title=title,
                    style='font-size: %s%%' % tag['size']
                ),
                nodes.Text(' ')
            ))
        return container


class TagList(Macro):
    """
    Show a taglist.
    """

    is_block_tag = True
    arguments = (
        ('tag', unicode, ''),
    )

    def __init__(self, active_tag):
        self.active_tag = active_tag

    def build_node(self, context, format):
        active_tag = self.active_tag
        if not active_tag and context.request:
            active_tag = context.request.GET.get('tag')
        result = nodes.List('unordered', class_='taglist')
        if active_tag:
            for page in Page.objects.find_by_tag(active_tag):
                item = nodes.ListItem([nodes.InternalLink(page)])
                result.children.append(item)
        else:
            for tag in Page.objects.get_tagcloud():
                link = nodes.Link('?' + url_encode({
                        'tag':  tag['name']
                    }), [nodes.Text(tag['name'])],
                    style='font-size: %s%%' % tag['size']
                )
                result.children.append(nodes.ListItem([link]))
        return result


class Include(Macro):
    """
    Include a page.  This macro works dynamically thus the included headlines
    do not appear in the TOC.
    """

    is_block_tag = True
    arguments = (
        ('page', unicode, ''),
        ('silent', bool, False)
    )

    def __init__(self, page, silent):
        self.page = page
        self.silent = silent
        self.context = []
        if self.page:
            self.metadata = [nodes.MetaData('X-Attach', ('/' + self.page,))]

    def build_node(self, context, format):
        parent_page = context.wiki_page
        try:
            page = Page.objects.get_by_name(self.page)
        except Page.DoesNotExist:
            if self.silent:
                return nodes.Text('')
            return nodes.error_box(u'Seite nicht gefunden',
                                   u'Die Seite „%s“ wurde nicht '
                                   u'gefunden.' % self.page)
        if not parent_page:
            parent_page = page
        if page.name in context.included_pages:
            return nodes.error_box(u'Zirkulärer Import',
                                   u'Rekursiver Aufruf des Include '
                                   u'Makros wurde erkannt.')
        context.included_pages.add(page.name)
        return page.rev.text.render(context=context, format=format)


class Template(Macro):
    """
    Include a page as template and expand it.
    """

    has_argument_parser = True
    is_static = True

    def __init__(self, args, kwargs):
        if not args:
            self.template = None
            return
        items = kwargs.items()
        for idx, arg in enumerate(args[1:]):
            items.append(('arguments.%d' % idx, arg))
        self.template = pagename_join(settings.WIKI_TEMPLATE_BASE, args[0])
        self.context = items

    def build_node(self):
        if self.template is None:
            return nodes.error_box(u'Parameterfehler', 'Das erste Argument '
                                   u'muss der Name des Templates sein.')
        try:
            page = Page.objects.get_by_name(self.template)
        except Page.DoesNotExist:
            return nodes.error_box(u'Fehlende Vorlage', u'Das gewünschte '
                                   u'Template existiert nicht.')
        return nodes.Container(page.rev.text.parse(self.context).children +
                               [nodes.MetaData('X-Attach', (self.template,))])


class Picture(Macro):
    """
    This macro can display external images and attachments as images.  It
    also takes care about thumbnail generation.  For any internal (attachment)
    image included that way an ``X-Attach`` metadata is emitted.

    Like for any link only absolute targets are allowed.  This might be
    surprising behavior if you're used to the MoinMoin syntax but caused
    by the fact that the parser does not know at parse time on which page
    it is operating.
    """

    arguments = (
        ('picture', unicode, u''),
        ('size', unicode, u''),
        ('align', unicode, u''),
        ('alt', unicode, u'')
    )

    def __init__(self, target, dimensions, alignment, alt):
        #: a image on another server
        self.is_http_link = is_http_link(target)
        #: a wiki attachment on a different page
        self.is_external = is_external_target(target)
        if not self.is_http_link:
            if not self.is_external:
                self.metadata = [nodes.MetaData('X-Attach', [target])]
            target = normalize_pagename(target)
        self.target = target
        self.alt = alt or target
        if dimensions:
            if 'x' in dimensions:
                width, height = dimensions.split('x', 1)
            else:
                width = dimensions
                height = ''
            try:
                self.width = int(width)
            except ValueError:
                self.width = None
            try:
                self.height = int(height)
            except ValueError:
                self.height = None
        else:
            self.width = self.height = None
        self.align = alignment
        if self.align not in ('left', 'right', 'center'):
            self.align = None

    def build_node(self, context, format):
        target = self.target
        if self.is_http_link:
            style = '%s%s' % (
                self.width and ('width: %spx;' % self.width) or '',
                self.height and ('height: %spx;' % self.height) or ''
            )
            return nodes.Image(target, self.alt, class_='image-' +
                               (self.align or 'default'), style=style or None)
        else:
            if not self.is_external and context.wiki_page:
                target = pagename_join(context.wiki_page, self.target)
            target = href('wiki', '_image',
                target=target,
                width=self.width,
                height=self.height
            )
            return nodes.Image(target, self.alt, class_='image-' +
                               (self.align or 'default'))


class Date(Macro):
    """
    This macro accepts an `iso8601` string or unix timestamp (the latter in
    UTC) and formats it using the `format_datetime` function.
    """

    arguments = (
        ('date', unicode, None),
    )

    def __init__(self, date):
        if not date:
            self.now = True
        else:
            self.now = False
            try:
                self.date = parse_iso8601(date)
            except ValueError:
                try:
                    self.date = datetime.utcfromtimestamp(int(date))
                except ValueError:
                    self.date = None

    def build_node(self, context, format):
        if self.now:
            date = datetime.utcnow()
        else:
            date = self.date
        if date is None:
            return nodes.Text(u'ungültiges Datum')
        return nodes.Text(format_datetime(date))


class NewPages(Macro):
    """
    This macro shows the latest wiki articles and orders them by the month of
    their creation.
    """

    arguments = (
        ('months', int, 3),
    )

    def __init__(self, months):
        self.months = months

    def build_node(self, context, format):
        now = datetime.utcnow()
        if now.month > self.months:
            date = datetime(now.year, now.month - self.months, 1)
        else:
            date = datetime(now.year - 1, 12 + now.month - self.months, 1)
        result = nodes.Container()
        last_month = None
        for page, change_date in Page.objects.get_recently_created(date):
            if change_date.month != last_month:
                last_month = change_date.month
                last_list = nodes.List('unordered')
                text = nodes.Text(change_date.strftime('%B'))
                headline = nodes.Headline(level=3, children=[text])
                result.children.extend([headline, last_list])
            title = [nodes.Text(get_title(page, True))]
            link = nodes.InternalLink(page, title, force_existing=True)
            last_list.children.append(nodes.ListItem([link]))
        return result


class Newline(Macro):
    """
    This macro just forces a new line.
    """

    is_static = True

    def build_node(self):
        return nodes.Newline()


class Anchor(Macro):
    """
    This macro creates an anchor accessible by url.
    """

    is_static = True
    arguments = (
        ('id', unicode, None),
    )

    def __init__(self, id):
        self.id = id

    def build_node(self):
        return nodes.Span(id=self.id)


#: this mapping is used by the `get_macro()` function to map public
#: macro names to the classes.
ALL_MACROS = {
    u'LetzteÄnderungen':    RecentChanges,
    u'Inhaltsverzeichnis':  TableOfContents,
    u'Seitenzahl':          PageCount,
    u'Seitenliste':         PageList,
    u'Anhänge':             AttachmentList,
    u'VerwaisteSeiten':     OrphanedPages,
    u'FehlendeSeiten':      MissingPages,
    u'Weiterleitungen':     RedirectPages,
    u'Seitenname':          PageName,
    u'ÄhnlicheSeiten':      SimilarPages,
    u'TagWolke':            TagCloud,
    u'TagListe':            TagList,
    u'Einbinden':           Include,
    u'Vorlage':             Template,
    u'Bild':                Picture,
    u'Datum':               Date,
    u'NeueSeiten':          NewPages,
    u'BR':                  Newline,
    u'Anker':               Anchor,
    u'NeueSeite':           NewPage
}


#: automatically updated reverse mapping of macros
REVERSE_MACROS = dict((v, k) for k, v in ALL_MACROS.iteritems())
