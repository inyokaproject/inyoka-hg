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
from cPickle import dumps, loads
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
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


class SearchResult(object):
    """
    This class holds all search results.
    """

    def __init__(self, mset, query, page, per_page, adapters={}):
        self.matches_estimated = mset.get_matches_estimated()
        self.page = page
        self.page_count = self.matches_estimated / per_page + 1
        self.per_page = per_page
        self.results = []
        for match in mset:
            full_id = match.get_document().get_value(0).split(':')
            adapter = adapters[full_id[0]]
            try:
                data = adapter.recv(full_id[1])
            except ObjectDoesNotExist:
                continue
            data['score'] = match[xapian.MSET_PERCENT]
            self.results.append(data)
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
        self.prefix_handlers = {}
        self.auth_deciders = {}
        self.adapters = {}

    def index(self, component, docid):
        self.adapters[component].store(docid)

    def queue(self, component, docid):
        from inyoka.portal.models import SearchQueue
        SearchQueue.objects.append(component, docid)

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

    def register(self, adapter):
        """
        Register a search adapter for indexing and retrieving.
        """
        if not adapter.type_id:
            raise ValueError('You must specify a type_id fot the adapter')
        self.adapters[adapter.type_id] = adapter
        if adapter.auth_decider:
            self.auth_deciders[adapter.type_id] = adapter.auth_decider

    def register_prefix_handler(self, prefixes, handler):
        """
        Register a prefix handler which can be used to search for
        spezific terms in the database. Instead of a simple prefix->value
        map, we use own handlers which can do additional transformations
        and database lookups, but they must all return a xapian.Query
        object (or None in case of failure).
        """
        for prefix in prefixes:
            self.prefix_handlers[prefix] = handler

    def parse_query(self, query):
        """Parse a query."""
        return QueryParser(self.prefix_handlers).parse(query)

    def query(self, user, query, page=1, per_page=20, date_begin=None,
              date_end=None, collapse=True, component=None):
        """Search for something."""
        enq = xapian.Enquire(self.get_connection())
        qry = self.parse_query(query)
        if component:
            qry = xapian.Query(xapian.Query.OP_FILTER, qry,
                               xapian.Query('P%s' % component.lower()))
        if date_begin or date_end:
            d1 = date_begin and mktime(date_begin.timetuple()) or 0
            d2 = date_end and mktime(date_end.timetuple()) or \
                 mktime(datetime.utcnow().timetuple())
            range = xapian.Query(xapian.Query.OP_VALUE_RANGE, 2,
                                 xapian.sortable_serialise(d1),
                                 xapian.sortable_serialise(d2))
            qry = xapian.Query(xapian.Query.OP_FILTER, qry, range)
        if collapse:
            enq.set_collapse_key(1)
        enq.set_query(qry)
        offset = (page - 1) * per_page

        auth = AuthMatchDecider(user, self.auth_deciders)
        mset = enq.get_mset(offset, per_page, per_page * 3, None, auth)

        return SearchResult(mset, qry, page, per_page, self.adapters)

    def store(self, **data):
        doc = xapian.Document()
        pos = 0

        # identification (required)
        full_id = (data['component'].lower(), data['uid'])
        doc.add_term('P%s' % full_id[0])
        doc.add_term('Q%s:%d' % full_id)
        doc.add_value(0, '%s:%d' % full_id)

        # collapse key (optional)
        if data.get('collapse'):
            doc.add_value(1, '%s:%s' % (full_id[0], data['collapse']))

        # title (optional)
        if data.get('title'):
            title = list(tokenize(data['title']))
            for token in title:
                doc.add_posting(token, pos)
                pos += 1
            pos += 20
            for token in title:
                doc.add_posting('T%s' % token, pos)
                pos += 1
            pos += 20

        # user (optional)
        if data.get('user'):
            doc.add_term('U%d' % data['user'])

        # date (optional)
        if data.get('date'):
            time = xapian.sortable_serialise(mktime(data['date'].timetuple()))
            doc.add_value(2, time)

        # authentification informations (optional)
        if data.get('auth'):
            doc.add_value(3, dumps(data['auth']))

        # category (optional)
        if data.get('category'):
            categories = data.get('category')
            if isinstance(categories, (str, unicode)):
                categories = [categories]
            for category in categories:
                doc.add_term('C%s' % category.lower())

        # text (optional, can contain multiple items)
        if data.get('text'):
            text = data['text']
            if isinstance(text, (str, unicode)):
                text = [text]
            for block in text:
                for token in tokenize(block):
                    doc.add_posting(token, pos)
                    pos += 1
                pos += 20

        connection = self.get_connection(True)
        connection.replace_document('Q%s:%d' % full_id, doc)

# setup the singleton instance
search = None
search = SearchSystem()


def search_handler(*prefixes):
    """A decorator which registers the search handler."""
    def decorate(f):
        search.register_prefix_handler(prefixes, f)
        return f
    return decorate


class AuthMatchDecider(xapian.MatchDecider):

    def __init__(self, user, deciders):
        xapian.MatchDecider.__init__(self)
        self.deciders = dict((k, d(user)) for k, d in deciders.iteritems())

    def __call__(self, doc):
        component = doc.get_value(0).split(':')[0]
        auth = doc.get_value(3)
        decider = self.deciders.get(component)
        if auth and decider is not None:
            return decider(loads(auth))
        else:
            # XXX:print "ignoring", doc.get_value(0), self.deciders
            pass
        return True


class SearchAdapter(object):
    type_id = None
    auth_decider = None

    @classmethod
    def queue(self, docid):
        from inyoka.portal.models import SearchQueue
        SearchQueue.objects.append(self.type_id, docid)

    def store(self, docid):
        raise NotImplementedError('store')

    def recv(self, docid):
        raise NotImplementedError('recv')
