# -*- coding: utf-8 -*-
"""
    inyoka.portal.search
    ~~~~~~~~~~~~~~~~~~~~

    Since the portal doesn't create and store searchable documents by its
    own this module only profides some general costumazions which are
    available trough the whole portal. For the concrete implementations
    have a look at the `inyoka.app.search` modules, where app is the
    name of the application.

    :copyright: Copyright 2007 by Christoph Hack.
    :license: GNU GPL.
"""
import xapian
from time import mktime
from inyoka.portal.user import User
from inyoka.utils.search import Document, tokenize, search_handler


class PortalDocument(Document):
    """
    This Document provides some document setters for general search
    attributes. However you shouldn't use this class directly, but you
    can subclass it and implement the associating getters to retrieve
    the information from the database (or to costumize the setters if
    needed).
    """
    type_id = 'portal'

    def __init__(self, docid=None):
        Document.__init__(self, docid)

    def set_title(self, title):
        """Tokenize and normalize the title and add it with an prefix."""
        title = list(tokenize(title))
        self.add_postings(title, prefix='T')
        self.add_postings(title)

    def set_area(self, area):
        """
        The area helps us to seperate the documents again. So it's
        for example possible to search for wiki documents only.
        """
        self.add_terms([area.strip().lower()], prefix='A')

    def set_author(self, user):
        """Set the author(s) for this document."""
        if isinstance(user, User):
            user = user.id
            self.add_terms((int(user),), prefix='U')

    def set_tags(self, tags):
        """You can add a list of tags for a tag-search."""
        tags = [tag.strip().lower() for tag in tags]
        self.add_terms(tags, prefix='X')
        self.add_terms(tags)

    def set_text(self, text):
        """
        Normaly the text simple gets tokenized and stemmed, but you can
        change this behavior if wanted.
        """
        self.add_postings(tokenize(text))

    def set_date(self, date):
        """
        Add the date as encoded timestamp to allow cronological sorting
        and for searching only in an spezified timeframe.
        """
        time = xapian.sortable_serialise(mktime(date.timetuple()))
        self._doc.add_value(1, time)

    def set_group(self, key):
        """
        If you want to group documents by an specific key (e.g. to group
        posts by topic or revisions by their pages, you can set this key.
        """
        self._doc.add_value(2, key)

    def get_highlight(self):
        """
        Return True if the destination url allows highlighting of search
        words or False otherwise.
        """
        return True


@search_handler(u'user', u'author')
def handle_user(username):
    """Look up the user id for an given given username."""
    try:
        user = User.objects.get(username__exact=username)
        return xapian.Query(u'U%d' % (user.id))
    except User.DoesNotExist:
        return None


@search_handler(u'title', u'titel')
def handle_title(title):
    """Tokenize words in the title automatically."""
    tokens = tokenize(title)
    query = None
    for token in tokens:
        if query is None:
            query = xapian.Query(u'T%s' % token)
        else:
            query = xapian.Query(xapian.Query.OP_AND, query,
                                 xapian.Query(u'T%s'%  token))
    return query


@search_handler(u'area', u'bereich')
def handle_area(area):
    """Normalize the name of the area."""
    map = {
        'forum': 'f',
        'wiki': 'w',
        'ikhaya': 'i',
        'planet': 'p',
    }
    component = map.get(area.strip().lower())
    return component and xapian.Query(u'P%s' % component)
