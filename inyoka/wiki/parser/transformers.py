# -*- coding: utf-8 -*-
"""
    inyoka.wiki.parser.transformers
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This module holds ast transformers we use.  Transformers can assume that
    they always operate on complete trees, thus the outermost node is always
    a container node.

    Transformers are not necessarily the last thing that processes a tree.
    For example macros that are marked as tree processors and have have their
    stage attribute set to 'final' are expanded after all the transformers
    finished their job.

    :copyright: Copyright 2007 by Armin Ronacher, Christoph Hack.
    :license: GNU GPL.
"""
import re
from inyoka.wiki.parser import nodes


_newline_re = re.compile(r'(\n)(?!$)')
_paragraph_re = re.compile(r'(\s*?\n){2,}')

_german_typography_rules = [
    (re.compile(r'(?<!\.)\.\.\.(?!\.)'), u'…'),
    (re.compile(r'(?<!-)---(?!-)'), u'—'),
    (re.compile(r'(?<!-)--(?!-)'), u'–'),
    (re.compile(r'\d(")(?u)'), u'″'),
    (re.compile(r'\d(\')(?u)'), u'′'),
    (re.compile(r'\+\-'), u'±'),
    (re.compile(r'\(c\)'), u'©'),
    (re.compile(r'\(R\)'), u'®'),
    (re.compile(r'\(TM\)'), u'™'),
    (re.compile(r'\d\s+(x)\s+\d(?u)'), u'×'),
    (re.compile(r'(?:^|\s)(\')(?u)'), u'‚'),
    (re.compile(r'\S(\')(?u)'), u'‘'),
    (re.compile(r'(?:^|\s)(")(?u)'), u'„'),
    (re.compile(r'\S(")(?u)'), u'“')
]


class Transformer(object):
    """
    Baseclass for all transformers.
    """

    def transform(self, tree):
        """
        This is passed a tree that should be processed.  A class can modify
        a tree in place, the return value has to be the tree then.  Otherwise
        it's safe to return a new tree.
        """
        return tree


class AutomaticParagraphs(Transformer):
    """
    This transformer is enabled per default and wraps elements in paragraphs.
    All macros and parsers depend on this parser so it's a terrible idea to
    disable this one.
    """

    def joined_text_iter(self, node):
        """
        This function joins multiple text nodes that follow each other into
        one.
        """
        text_buf = []

        def flush_text_buf():
            if text_buf:
                text = u''.join(text_buf)
                if text:
                    yield nodes.Text(text)
                del text_buf[:]

        for child in node.children:
            if child.is_text_node:
                text_buf.append(child.text)
            else:
                for item in flush_text_buf():
                    yield item
                yield child
        for item in flush_text_buf():
            yield item

    def break_lines(self, text, last_node_hint=None):
        """
        This function sets soft line breaks which are also possible in
        sections where paragraphs are not supported as line breaks are
        inline elements.  The last_node_hint is used to avoid line breaks
        after block level elements.  If None an inline node is assumed.
        """
        ignore_next = last_node_hint is not None \
                      and not last_node_hint.is_block_tag
        result = []
        for piece in _newline_re.split(text):
            if piece == '\n':
                if not ignore_next:
                    ignore_next = False
                else:
                    result.append(nodes.Newline())
            elif piece:
                result.append(nodes.Text(piece))
                ignore_next = False
        return result

    def set_paragraphs(self, parent):
        """
        Insert real paragraphs into the node and return it.
        """
        paragraphs = [[]]

        for child in self.joined_text_iter(parent):
            if child.is_text_node:
                blockiter = iter(_paragraph_re.split(child.text))
                for block in blockiter:
                    try:
                        is_paragraph = blockiter.next()
                    except StopIteration:
                        is_paragraph = False
                    if block:
                        paragraphs[-1].extend(self.break_lines(block,
                                              paragraphs[-1] and \
                                              paragraphs[-1][-1] or None))
                    if is_paragraph:
                        paragraphs.append([])
            elif child.is_block_tag:
                paragraphs.extend((child, []))
            else:
                paragraphs[-1].append(child)

        del parent.children[:]
        for paragraph in paragraphs:
            if not isinstance(paragraph, list):
                parent.children.append(paragraph)
            else:
                for node in paragraph:
                    if not node.is_text_node or node.text:
                        parent.children.append(nodes.Paragraph(paragraph))
                        break

        return parent

    def transform(self, parent):
        """Sets linebreaks and paragraphs."""
        # first we recurse to all the children.  We do that in the head
        # so that the paragraph and linebreak rewriters can already work
        # with the modified children
        for node in parent.children:
            if node.is_container and not node.is_raw:
                self.transform(node)

        # if a node does not support paragraphs (usually inline nodes)
        # we still rewrite the children's text nodes but just for
        # linebreaks and not paragraphs.
        if not parent.allows_paragraphs:
            new_children = []
            for child in self.joined_text_iter(parent):
                if child.is_text_node:
                    hint = new_children and new_children[-1] or None
                    new_children.extend(self.break_lines(child.text, hint))
                else:
                    new_children.append(self.transform(child))
            parent.children[:] = new_children
            return parent

        # At this point we now set the paragraphs for the node as
        # this node supports supports paragraphs.
        return self.set_paragraphs(parent)


class GermanTypography(Transformer):
    """
    This class enables German typography for a tree.  Basically simple inch
    signs and other quotes are replaced with typographically correct quotes.
    """

    def transform(self, tree):
        def handle_match(match):
            all = match.group()
            if not match.groups():
                return replacement
            offset = match.start()
            return all[:match.start(1) - offset] + \
                   replacement + \
                   all[match.end(1) - offset:]

        if tree.is_container and not tree.is_raw:
            for node in tree.children:
                if node.is_text_node:
                    for regexp, replacement in _german_typography_rules:
                        node.text = regexp.sub(handle_match, node.text)
                elif node.is_container:
                    self.transform(node)
        return tree


class SmileyInjector(Transformer):
    """
    Adds smilies from the configuration.
    """

    def __init__(self, smiley_set=None):
        self.smiley_set = smiley_set

    def transform(self, tree):
        if self.smiley_set is not None:
            smilies = self.smiley_set
        else:
            from inyoka.wiki.storage import storage
            smilies = dict(storage.smilies)
        if not smilies:
            return tree
        smiley_re = re.compile(r'(?:^|[^\w\d])(%s)(?:$|[^\w\d])(?u)' %
                               '|'.join(re.escape(s) for s in sorted(smilies,
                                        key=lambda x: -len(x))))

        new_children = []
        for node in tree.children:
            new_children.append(node)
            if node.is_container and not node.is_raw:
                self.transform(node)
            elif node.is_text_node and not node.is_raw:
                pos = 0
                text = node.text
                for match in smiley_re.finditer(text):
                    node.text = text[pos:match.start(1)]
                    code = match.group(1)
                    pos = match.end(1)
                    node = nodes.Text()
                    new_children.extend((
                        nodes.Image(smilies[code], code),
                        node
                    ))
                if pos and text[pos:]:
                    node.text = text[pos:]
                if not node.text:
                    new_children.pop()
        tree.children[:] = new_children
        return tree


class FootnoteSupport(Transformer):
    """
    Looks for footnote nodes, gives them an unique id and moves the
    text to the bottom into a list.  Without this translator footnotes
    are just <small>ed and don't have an id.
    """

    def transform(self, tree):
        footnotes = []
        for footnote in tree.query.by_type(nodes.Footnote):
            footnotes.append(footnote)
            footnote.id = len(footnotes)

        if footnotes:
            container = nodes.List('unordered', class_='footnotes')
            for footnote in footnotes:
                backlink = nodes.Link('#bfn-%d' % footnote.id,
                                      [nodes.Text(unicode(footnote.id))],
                                      id='fn-%d' % footnote.id)
                node = nodes.ListItem([backlink, nodes.Text(': ')] +
                                      footnote.children)
                container.children.append(node)
            tree.children.append(container)
        return tree


class HeadlineProcessor(Transformer):
    """
    This transformer looks at all headlines and makes sure that every ID is
    unique.  If one id clashes with another headline ID a numeric suffix is
    added.  What this transformer does not do is resolving clashes with
    footnotes or other references.  At least not by now because such clashes
    are very unlikely.
    """

    def transform(self, tree):
        id_map = {}
        for headline in tree.query.by_type(nodes.Headline):
            while 1:
                if not headline.id:
                    headline.id = 'empty-headline'
                if headline.id not in id_map:
                    id_map[headline.id] = 1
                    break
                else:
                    id_map[headline.id] += 1
                    headline.id += '-%d' % id_map[headline.id]
        return tree


class AutomaticStructure(Transformer):
    """
    This transformer adds additional structure information.  Each headline
    adds either a new section or subsection depending on its level.  This is
    required for docbook, but might be useful for HTML too, if you want to
    indent paragraphs depending on their level.
    """

    def transform(self, tree):
        if not tree.is_container:
            return tree
        struct = [[]]
        for node in tree.children:
            if isinstance(node, nodes.Headline):
                while node.level < len(struct):
                    struct.pop()
                while node.level > len(struct)-1:
                    sec = nodes.Section(len(struct))
                    struct[-1].append(sec)
                    struct.append(sec.children)
            struct[-1].append(node)
        tree.children = struct[0]
        return tree


DEFAULT_TRANSFORMERS = [AutomaticParagraphs(), GermanTypography(),
                        SmileyInjector(), FootnoteSupport(),
                        HeadlineProcessor(), AutomaticStructure()]
