# -*- coding: utf-8 -*-
"""
    inyoka.wiki.search
    ~~~~~~~~~~~~~~~~~~

    Implements the search system for the wiki. The update procedure is
    automatically started by the `Page.save()` method so there is no need
    to work with this by hand.

    Currently we only push the most recent version into the search index,
    older revisions are automatically removed. This won't change for multiple
    reasons, the most important one is that this is consistent with the
    metadata which is always bound to the page object not a specific revision.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from django.core.exceptions import ObjectDoesNotExist
from inyoka.portal.search import PortalDocument
from inyoka.wiki.models import Page


class WikiDocument(PortalDocument):
    """
    A document which knows how to index special wiki attributes and how
    to find them again.
    """
    type_id = 'wiki'

    def __init__(self, docid=None):
        PortalDocument.__init__(self, docid)
        self.wikipage = None
        if self.docid is not None:
            self.wikipage = Page.objects.get(xapian_docid=self.docid)
            self.wikipage.rev = self.wikipage.revisions.latest()
            if self.wikipage.rev.deleted:
                raise ObjectDoesNotExist()

    def get_author(self):
        return self.wikipage.rev.user

    def get_author_url(self):
        return self.wikipage.rev.user.get_absolute_url()

    def get_text(self):
        return self.wikipage.rev.text

    def get_title(self):
        return self.wikipage.name

    def get_date(self):
        return self.wikipage.rev.change_date

    def get_tags(self):
        # TODO: Lookup related tags in the metadata and return them
        return None

    def get_area(self):
        return u'Wiki'

    def get_absolute_url(self):
        return self.wikipage.get_absolute_url()
