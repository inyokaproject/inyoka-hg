#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.search_update
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This scripts updates the search index by (re)indexing the documents
    of `portal_searchqueue`.

    If the search index is not existent when starting this script, it
    automatically gets created; afterwards the index is completely generated
    for all documents of all components.

    :copyright: 2007 - 2008 by Christoph Hack, Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
import gc, sys, datetime
from xapian import DatabaseOpeningError
import inyoka.utils.http
from inyoka import application
from django.db import connection
from django.db.models import get_app, get_models
from inyoka.portal.models import SearchQueue
from inyoka.utils.search import search
from inyoka.utils.database import session

# import required adapters
import inyoka.forum.search
import inyoka.planet.models
import inyoka.wiki.search
import inyoka.ikhaya.models


def update():
    """
    Update the next items from the queue.  You should call this
    function regularly (e.g. as cron).
    """
    for i, doc in enumerate(SearchQueue.objects.select_blocks()):
        search.index(doc[0], doc[1])
        if i % 100 == 0:
            search.flush()
        search.flush()
        session.remove()


def reindex(app=None):
    """Update the search index by reindexing all tuples from the database."""
    for comp, adapter in search.adapters.iteritems():
        print "\n\n"
        print "---------- indexing %s -----------------" % comp
        print "starting at %s" % datetime.datetime.now()
        print
        sys.stdout.flush()
        connection.queries = []
        gc.collect()
        for i, doc_id in enumerate(adapter.get_doc_ids()):
            search.index(comp, doc_id)
            if i % 100 == 0:
                search.flush()
                if i / 100 == 50:
                    print
                sys.stdout.write('.')
                sys.stdout.flush()
        search.flush()
        session.remove()



if __name__ == '__main__':
    try:
        search.get_connection()
    except DatabaseOpeningError:
        print 'Search index does not exist, creating a new one'
        search.get_connection(True)
        print 'Starting to reindex everything'
        reindex()
    update()
