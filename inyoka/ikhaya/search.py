# -*- coding: utf-8 -*-
"""
    inyoka.ikhaya.search
    ~~~~~~~~~~~~~~~~~~~~

    Implements the search system for ikhaya.

    :copyright: Copyright 2007 by Benjamin Wiegand, Christoph Hack
    :license: GNU GPL.
"""
from inyoka.portal.search import PortalDocument
from inyoka.ikhaya.models import Article


class IkhayaDocument(PortalDocument):
    """
    We're the ikhaya!
    """
    type_id = 'ikhaya'

    def __init__(self, docid=None):
        PortalDocument.__init__(self, docid)
        self.article = None
        if self.docid:
            self.article = Article.objects.get(xapian_docid=self.docid)

    def get_title(self):
        return self.article.subject

    def get_author(self):
        return self.article.author

    def get_author_url(self):
        return self.article.author.get_absolute_url()

    def get_date(self):
        return self.article.pub_date

    def get_area(self):
        return u'Ikhaya'

    def get_absolute_url(self):
        return self.article.get_absolute_url()
