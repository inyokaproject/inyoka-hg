# -*- coding: utf-8 -*-
"""
    inyoka.planet.search
    ~~~~~~~~~~~~~~~~~~~~

    Implements the search system for the planet.

    :copyright: Copyright 2007 by Christoph Hack, Benjamin Wiegand.
    :license: GNU GPL.
"""
from inyoka.planet.models import Entry
from inyoka.portal.search import PortalDocument


class PlanetDocument(PortalDocument):
    """
    Represents one post from the planet in the search database.
    """
    type_id = 'planet'

    def __init__(self, docid=None):
        PortalDocument.__init__(self, docid)
        self.entry = None
        if self.docid:
            self.entry = Entry.objects.get(xapian_docid=self.docid)

    def get_title(self):
        return self.entry.title

    def get_date(self):
        return self.entry.updated

    def get_area(self):
        return u'Planet'

    def get_absolute_url(self):
        return self.entry.get_absolute_url()

    def get_author(self):
        return self.entry.blog.name

    def get_author_url(self):
        return self.entry.blog.blog_url

    def get_highlight(self):
        return False
