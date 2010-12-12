# -*- coding: utf-8 -*-
"""
    inyoka.utils.highlight
    ~~~~~~~~~~~~~~~~~~~~~~

    This module summarizes various highlighting tasks.  Right now it implements:

     * code highlighting using `Pygments <http://pygments.org>`
     * Text excerpt highlighting used by the search system.

    The text excerpt highlighting system is borrowd from `Xappy <code.google.com/p/xappy>`
    but heavily modified to fix soem bugs and to match inyoka search internals.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import re
import xapian
from pygments import highlight
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename, \
    get_lexer_for_mimetype, TextLexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound
from pygments.styles.friendly import FriendlyStyle
from inyoka.utils.search import get_stemmer, LANGUAGE
from inyoka.utils.html import striptags


_pygments_formatter = HtmlFormatter(style='colorful', cssclass='syntax',
                                    linenos='table')

# split string into words, spaces, punctuation and markup tags
_split_re = re.compile(r'<\w+[^>]*>|</\w+>|[\w\']+|\s+|[^\w\'\s<>/]+')

# regular expression for the tested for box
_tested_for_re = re.compile(r'<div class="box tested_for">(.+?)</div>', re.M | re.S)


def highlight_code(code, lang=None, filename=None, mimetype=None):
    """Highlight a block using pygments to HTML."""
    try:
        lexer = None
        guessers = [(lang, get_lexer_by_name),
            (filename, get_lexer_for_filename),
            (mimetype, get_lexer_for_mimetype)
        ]
        for var, guesser in guessers:
            if var is not None:
                try:
                    lexer = guesser(var, stripnl=False, startinline=True)
                    break
                except ClassNotFound: continue

        if lexer is None:
            lexer = TextLexer(stripnl=False)
    except LookupError:
        lexer = TextLexer(stripnl=False)
    return highlight(code, lexer, _pygments_formatter)


class HumanStyle(FriendlyStyle):
    """
    This is a pygments style that matches the ubuntuusers design.
    """


class TextHighlighter(object):
    """Class for highlighting text and creating contextual summaries.

    >>> hl = Highlighter("en")
    >>> hl.make_sample('Hello world.', ['world'])
    'Hello world.'
    >>> hl.highlight('Hello world', ['world'], ('<', '>'))
    'Hello <world>'

    """
    def __init__(self, language_code=LANGUAGE, stemmer=None):
        if stemmer is not None:
            self._stem = stemmer
        else:
            self._stem = get_stemmer(language_code)
        self._terms = None
        self._query = None

    def stem(self, word):
        return self._stem(word)

    def _split_text(self, text, strip_tags=False):
        """Split some text into words and non-words.

        - `text` is the text to process.  It may be a unicode object or a utf-8
          encoded simple string.
        - `strip_tags` is a flag - False to keep tags, True to strip all tags
          from the output.

        Returns a list of utf-8 encoded simple strings.

        """
        text = text.replace('<br />', ' ').replace('<p>', ' ')
        if strip_tags:
            text = striptags(text)
        return _split_re.findall(text)

    def _strip_prefix(self, term):
        """Strip the prefix off a term.

        Prefixes are any initial capital letters, with the exception that R always
        ends a prefix, even if followed by capital letters.

        >>> hl = Highlighter("en")
        >>> print hl._strip_prefix('hello')
        hello
        >>> print hl._strip_prefix('Rhello')
        hello
        >>> print hl._strip_prefix('XARHello')
        Hello
        >>> print hl._strip_prefix('XAhello')
        hello
        >>> print hl._strip_prefix('XAh')
        h
        >>> print hl._strip_prefix('XA')
        <BLANKLINE>

        """
        for p in xrange(len(term)):
            if term[p].islower():
                return term[p:]
            elif term[p] == 'R':
                return term[p+1:]
        return u''

    def _query_to_stemmed_words(self, query):
        """Convert a query to a list of stemmed words.

        Stores the resulting list in self._terms

        - `query` is the query to parse: it may be xapian.Query object, or a
          sequence of terms.

        """
        if self._query is query:
            return

        if hasattr(query, '_get_xapian_query'):
            query = query._get_xapian_query()

        if isinstance(query, xapian.Query):
            terms = []
            iter = query.get_terms_begin()
            while iter != query.get_terms_end():
                term = iter.get_term()
                if term.islower():
                    terms.append(term)
                iter.next()
        else:
            terms = [self._stem(q.lower()) for q in query]

        self._terms = terms
        self._query = query

    def make_sample(self, text, query, maxlen=600, hl=None):
        """Make a contextual summary from the supplied text.

        This basically works by splitting the text into phrases, counting the query
        terms in each, and keeping those with the most.

        Any markup tags in the text will be stripped.

        `text` is the source text to summarise.
        `query` is either a Xapian query object or a list of (unstemmed) term strings.
        `maxlen` is the maximum length of the generated summary.
        `hl` is a pair of strings to insert around highlighted terms, e.g. ('<b>', '</b>')

        """

        # coerce maxlen into an int, otherwise truncation doesn't happen
        maxlen = int(maxlen)

        words = self._split_text(text, True)
        self._query_to_stemmed_words(query)

        # build blocks delimited by puncuation, and count matching words in each block
        # blocks[n] is a block [firstword, endword, charcount, termcount, selected]
        blocks = []
        start = end = count = blockchars = 0

        while end < len(words):
            blockchars += len(words[end])
            if words[end].isalnum():
                if self._stem(words[end].lower()) in self._terms:
                    count += 1
                end += 1
            elif words[end] in u',.?!\n':
                end += 1
                blocks.append([start, end, blockchars, count, False])
                start = end
                blockchars = 0
                count = 0
            else:
                end += 1
        if start != end:
            blocks.append([start, end, blockchars, count, False])
        if len(blocks) == 0:
            return u''

        # select high-scoring blocks first, down to zero-scoring
        chars = 0
        for count in xrange(3, -1, -1):
            for b in blocks:
                if b[3] >= count:
                    b[4] = True
                    chars += b[2]
                    if chars >= maxlen: break
            if chars >= maxlen: break

        # assemble summary
        words2 = ['<p>']
        lastblock = -1
        for i, b in enumerate(blocks[2:]):
            if b[4]:
                words2.append(u'<p>')
                if i != lastblock + 1:
                    words2.append(u'...')
                words2.extend(words[b[0]:b[1]])
                lastblock = i
                words2.append(u'</p>')

        if not blocks[-1][4]:
            words2.append(u'...')

        # trim down to maxlen
        l = 0
        for i in xrange (len (words2)):
            l += len (words2[i])
            if l >= maxlen:
                words2[i:] = [u'...']
                break

        # filter out empty word-blocks
        words = [word for word in words2 if not word.strip() == '...']

        if hl is None:
            return u''.join(words)
        else:
            return self._hl(words, hl)

    def highlight(self, text, query, hl, strip_tags=False):
        """Add highlights (string prefix/postfix) to a string.

        `text` is the source to highlight.
        `query` is either a Xapian query object or a list of (unstemmed) term strings.
        `hl` is a pair of highlight strings, e.g. ('<i>', '</i>')
        `strip_tags` strips HTML markout iff True

        >>> hl = Highlighter()
        >>> qp = xapian.QueryParser()
        >>> q = qp.parse_query('cat dog')
        >>> tags = ('[[', ']]')
        >>> hl.highlight('The cat went Dogging; but was <i>dog tired</i>.', q, tags)
        'The [[cat]] went [[Dogging]]; but was <i>[[dog]] tired</i>.'

        """
        words = self._split_text(text, strip_tags)
        self._query_to_stemmed_words(query)
        return self._hl(words, hl)

    def _score_text(self, text, prefix, callback):
        """Calculate a score for the text, assuming it was indexed with the
        given prefix.  `callback` is a callable which returns a weight for a
        term.

        """
        words = self._split_text(text, False)
        score = 0
        for w in words:
            wl = w.lower()
            score += callback(prefix + wl)
            score += callback(prefix + self._stem(wl))
        return score

    def _hl(self, words, hl):
        """Add highlights to a list of words.

        `words` is the list of words and non-words to be highlighted..

        """
        for i, w in enumerate(words):
            # HACK - more forgiving about stemmed terms
            wl = w.lower()
            if wl in self._terms or \
               self._stem(wl) in self._terms:
                words[i] = u''.join((hl[0], w, hl[1]))

        return u''.join(words)


def create_excerpt(text, query, tags=None, language=None, stemmer=None, strip_tags=False):
    if tags is None:
        tags = [u'<strong>', u'</strong>']
    # Strip the tested for box from highlighting so that we get better results
    # on wiki pages
    text = _tested_for_re.sub(u'', text)
    highlighter = TextHighlighter(language, stemmer)
    return highlighter.make_sample(text, query, 250, tags)
