# -*- coding: utf-8 -*-
"""
    inyoka.forum.search
    ~~~~~~~~~~~~~~~~~~~

    Implements the search system for the forum.

    :copyright: Copyright 2007 by Christoph Hack
    :license: GNU GPL.
"""
import xapian
from inyoka.portal.search import PortalDocument, search_handler
from inyoka.forum.models import Post


class ForumDocument(PortalDocument):
    """
    The document for the forum.
    """
    type_id = 'forum'

    def __init__(self, docid=None):
        PortalDocument.__init__(self, docid)
        self.post = None
        if self.docid:
            self.post = Post.objects.get(xapian_docid=self.docid)

    def get_title(self):
        return self.post.topic.title

    def get_author(self):
        return self.post.author

    def get_author_url(self):
        return self.post.author.get_absolute_url()

    def get_date(self):
        return self.post.pub_date

    def get_area(self):
        return u'Forum'

    def get_absolute_url(self):
        return self.post.get_absolute_url()

    def set_topic(self, value):
        self['group'] = 'F%d' % value
        self._doc.add_term('F%d' % value)


@search_handler('topic')
def handle_topic_id(value):
    try:
        return xapian.Query(u'F%d' % int(value))
    except ValueError:
        return None
