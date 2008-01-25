# -*- coding: utf-8 -*-
"""
    inyoka.utils.search
    ~~~~~~~~~~~~~~~~~~~

    This module implements an extensible search interface for all components
    of the inyoka system. For the concrete implementations have a look at the
    `inyoka.app.search` modules, where app is the name of the application.

    :copyright: Copyright 2007 by Armin Ronacher, Christoph Hack.
    :license: GNU GPL.
"""
import re
import xapian
from weakref import WeakKeyDictionary
from threading import currentThread as get_current_thread
from time import mktime
from datetime import datetime
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from inyoka.utils.parsertools import TokenStream


_word_re = re.compile(r'\w+(?u)')

_token_re = re.compile(r'''(?x)
    (?P<operator>[()-])     |
    (?P<termdef>[a-zA-Z]+:) |
    (?P<string>"[^"]*")     |
    (?P<arg>[^\s()]+)
''')

_keywords = {
    'ODER':     'or',
    'NICHT':    'not',
    'UND':      'and',
    'OR':       'or',
    'NOT':      'not',
    'AND':      'and'
}

_stemmer = xapian.Stem('de')
search = None


def stem(word):
    """Stem a single word."""
    return _stemmer(word.lower().encode('utf-8'))


def tokenize(text):
    """Tokenize and encode to utf-8."""
    for match in _word_re.finditer(text):
        yield stem(match.group())


class QueryParser(object):
    """
    Parse queries into xapian queries.
    """

    def __init__(self, term_defs=None, default_op=xapian.Query.OP_AND):
        self.term_defs = term_defs or {}
        self.default_op = default_op
        self.term_pos = 0

    def tokenize(self, query):
        """Helper function to tokenize"""
        for match in _token_re.finditer(query):
            for key, value in match.groupdict().iteritems():
                if value is not None:
                    if key == 'arg' and value in _keywords:
                        yield 'keyword', _keywords[value]
                    elif key == 'string':
                        yield 'longarg', value[1:-1]
                    elif key == 'termdef':
                        yield key, value[:-1]
                    else:
                        yield key, value
                    break

    def parse(self, query):
        """Parse a string into a xapian query."""
        stream = TokenStream.from_tuple_iter(self.tokenize(query))
        return self.parse_default(stream)

    def parse_default(self, stream, paren_expr=False):
        args = []
        while not stream.eof:
            if paren_expr and stream.current.type == 'operator' and \
               stream.current.value == ')':
                stream.next()
                break
            args.append(self.parse_or(stream))
        if not args:
            return xapian.Query()
        elif len(args) == 1:
            return args[0]
        return reduce(lambda a, b: xapian.Query(self.default_op, a, b), args)

    def parse_or(self, stream):
        q = self.parse_and(stream)
        while stream.current.type == 'keyword' and \
              stream.current.value == 'or':
            stream.next()
            q = xapian.Query(xapian.Query.OP_OR, q, self.parse_and(stream))
        return q

    def parse_and(self, stream):
        q = self.parse_not(stream)
        while stream.current.type == 'keyword' and \
              stream.current.value == 'and':
            stream.next()
            if stream.current.type == 'keyword' and \
               stream.current.value == 'not':
                stream.next()
                op = xapian.Query.OP_AND_NOT
            else:
                op = xapian.Query.OP_AND
            q = xapian.Query(op, q, self.parse_not(stream))
        return q

    def parse_not(self, stream):
        q = self.parse_primary(stream)
        while (stream.current.type == 'keyword' and
               stream.current.value == 'not') or \
              (stream.current.type == 'operator' and
               stream.current.value == '-'):
            stream.next()
            q = xapian.Query(xapian.Query.OP_AND_NOT, q,
                             self.parse_primary(stream))
        return q

    def parse_primary(self, stream):
        while not stream.eof:
            if stream.current.type == 'arg':
                word = stem(stream.current.value)
                stream.next()
                self.term_pos += 1
                return xapian.Query(word, 1, self.term_pos)
            elif stream.current.type == 'longarg':
                nodes = []
                for value in stream.current.value.split():
                    self.term_pos += 1
                    nodes.append(xapian.Query(stem(value), 1,
                                              self.term_pos))
                stream.next()
                return xapian.Query(xapian.Query.OP_PHRASE, nodes)
            elif stream.current.type == 'termdef':
                term_def = stream.current.value
                stream.next()
                if stream.current.type in ('arg', 'longarg'):
                    handler = self.term_defs.get(term_def)
                    if not handler:
                        continue
                    try:
                        qry = handler(stream.current.value)
                        if qry is not None:
                            return qry
                    finally:
                        stream.next()
                else:
                    continue
            elif stream.current.type == 'operator':
                if stream.current.value == '(':
                    stream.next()
                    return self.parse_default(stream, paren_expr=True)
                else:
                    stream.next()
            else:
                stream.next()
        return xapian.Query()


class DocumentMeta(type):
    """
    Metaclass for collecting the getter and setter methods. In
    addition, the document type gets registered.
    """
    def __new__(cls, name, bases, dct):
        setters = {}
        getters = {}
        ndct = {}
        for base in reversed(bases):
            if isinstance(base, DocumentMeta):
                setters.update(base._setters)
                getters.update(base._getters)
        for key, value in dct.iteritems():
            if key.startswith('set_'):
                setters[key[4:]] = value
            elif key.startswith('get_') and key != 'get_absolute_url':
                getters[key[4:]] = value
            else:
                ndct[key] = value
        ndct['_setters'] = setters
        ndct['_getters'] = getters
        assert ndct.get('type_id'), \
               'Each Document must have an unique type id!'
        doctype = type.__new__(cls, name, bases, ndct)
        if search is not None:
            search.register(doctype)
        return doctype


class Document(object):
    """
    Wraps a Xapian Document. Implementions should subclass this.
    """
    __metaclass__ = DocumentMeta
    type_id = 'doc'

    def __init__(self, docid=None):
        self.docid = docid or None
        if self.docid:
            connection = search.get_connection()
            try:
                self._doc = connection.get_document(self.docid)
            except xapian.DocNotFoundError:
                self._doc = xapian.Document()
        else:
            self._doc = xapian.Document()
        self._termpos = 0

    def clear(self):
        """Call this when reusing a document."""
        self._doc = xapian.Document()
        self._termpos = 0

    def save(self):
        """Save the changes on this document."""
        self._doc.add_value(0, self.type_id)
        connection = search.get_connection(True)
        if self.docid is None:
            self.docid = connection.add_document(self._doc)
        else:
            connection.replace_document(self.docid, self._doc)
        connection.flush()
        return self.docid

    def delete(self):
        """Delete this document from the database."""
        assert self.docid is not None
        connection = search.get_connection(True)
        connection.delete_document(self.docid)

    def add_postings(self, stream, prefix=''):
        """
        Add all postings from the stream in the right order. All postings
        and the prefix (if given) must be normalized!
        """
        for posting in stream:
            if isinstance(posting, unicode):
                posting = posting.encode('utf-8')
            self._doc.add_posting('%s%s' % (prefix, posting), self._termpos)
            self._termpos += 1
        self._termpos += 15

    def add_terms(self, stream, prefix=''):
        """
        Add all terms from the stream, extended with the given prefix. All
        terms and the prefix (if given) must be normalized!
        """
        for term in stream:
            if isinstance(term, unicode):
                term = term.encode('utf-8')
            self._doc.add_term('%s%s' % (prefix, term))

    def set_score(self, value):
        self._score = value

    def get_score(self):
        return self._score

    def get_doctype(self):
        return self.type_id

    def __getitem__(self, name):
        getter = self._getters.get(name)
        if getter is not None:
            return getter(self)
        return None

    def __setitem__(self, name, value):
        setter = self._setters.get(name)
        if setter is None:
            raise AttributeError, 'No setter for item "%s"' % name
        setter(self, value)


class SearchResult(object):
    """
    This class holds all search results.
    """

    def __init__(self, mset, query, page, per_page):
        self.matches_estimated = mset.get_matches_estimated()
        self.page = page
        self.page_count = self.matches_estimated / per_page + 1
        self.per_page = per_page
        self.results = []
        for match in mset:
            doc = search.get_document(match.get_docid())
            if doc is None or doc.type_id == 'doc':
                continue
            doc['score'] = match[xapian.MSET_PERCENT]
            self.results.append(doc)
        self.terms = []
        t = query.get_terms_begin()
        while t != query.get_terms_end():
            term = t.get_term()
            if term.islower():
                self.terms.append(term)
            t.next()

    @property
    def highlight_string(self):
        return ' '.join(term for term in self.terms)


class SearchSystem(object):
    """
    The central object that is used by applications to register their
    search interfaces.
    """

    def __init__(self):
        if search is not None:
            raise TypeError('cannot create %r instances, use the search '
                            "object instead" % self.__class__.__name__)
        self.connections = WeakKeyDictionary()
        self.doctypes = {}
        self.prefix_handlers = {}

    def get_connection(self, writeable=False):
        """Get a new connection to the database."""
        if writeable:
            return xapian.WritableDatabase(settings.XAPIAN_DATABASE,
                                           xapian.DB_CREATE_OR_OPEN)
        thread = get_current_thread()
        if thread not in self.connections:
            self.connections[thread] = connection = \
                xapian.Database(settings.XAPIAN_DATABASE)
        else:
            connection = self.connections[thread]
            connection.reopen()
        return connection

    def register(self, doctype):
        """Register a new document type."""
        self.doctypes[doctype.type_id] = doctype

    def register_handler(self, prefixes, handler):
        """
        Register a prefix handler which can be used to search for
        spezific terms in the database. Instead of a simple prefix->value
        map, we use own handlers which can do additional transformations
        and database lookups, but they must all return a xapian.Query
        object (or None in case of failure).
        """
        for prefix in prefixes:
            self.prefix_handlers[prefix] = handler

    def get_document(self, docid):
        db = self.get_connection()
        xapdoc = db.get_document(docid)
        doctype = self.doctypes.get(xapdoc.get_value(0), Document)
        try:
            return doctype(docid)
        except ObjectDoesNotExist:
            pass
            # delete document automatically?
        return None

    def create_document(self, doctype, docid=None):
        return self.doctypes.get(doctype, Document)(docid)

    def parse_query(self, query):
        """Parse a query."""
        return QueryParser(self.prefix_handlers).parse(query)

    def query(self, query, page=1, per_page=20, date_begin=None,
              date_end=None, collapse=True):
        """Search for something."""
        enq = xapian.Enquire(self.get_connection())
        qry = self.parse_query(query)
        if date_begin or date_end:
            d1 = date_begin and mktime(date_begin.timetuple()) or 0
            d2 = date_end and mktime(date_end.timetuple()) or \
                 mktime(datetime.now().timetuple())
            range = xapian.Query(xapian.Query.OP_VALUE_RANGE, 1,
                                 xapian.sortable_serialise(d1),
                                 xapian.sortable_serialise(d2))
            qry = xapian.Query(xapian.Query.OP_FILTER, qry, range)
        if collapse:
            enq.set_collapse_key(2)
        enq.set_query(qry)
        offset = (page - 1) * per_page
        mset = enq.get_mset(offset, per_page, per_page * 3)
        return SearchResult(mset, qry, page, per_page)


# setup the singleton instance
search = None
search = SearchSystem()


def search_handler(*prefixes):
    """A decorator which registers the search handler."""
    def decorate(f):
        search.register_handler(prefixes, f)
        return f
    return decorate
