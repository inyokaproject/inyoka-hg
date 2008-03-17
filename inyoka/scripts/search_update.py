#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.search_update
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Update the whole search index by reindexing all tuples from all
    Models providing a ``update_search`` method.  Normally you must not
    call this script, but it could be useful for fixing troubles
    with broken search indexes.

    If you only want to reindex a single application, make sure that the
    application is in your INSTALLED_APPS setting and run this script
    with the name of the application as an additional argument.


    :copyright: 2007 by Christoph Hack.
    :license: GNU GPL, see LICENSE for more details.
"""
from django.db.models import get_app, get_models
from inyoka.portal.models import SearchQueue
from inyoka.utils.search import search

# import required adapters
import inyoka.forum.search
import inyoka.planet.models
import inyoka.wiki.search
import inyoka.ikhaya.models


def update(limit=None):
    """
    Update the next items from the queue.  You should call this
    function regularly (e.g.  as cron).
    """
    last_id = 0
    for id, component, doc_id in SearchQueue.objects.next():
        search.index(component, doc_id)
        last_id = id
    search.flush()
    SearchQueue.objects.remove(last_id)


def reindex(app=None):
    """Update the search index by reindexing all tuples from the database."""
    if app is not None:
        app = get_app(app)
    for model in get_models(app):
        if not hasattr(model, 'update_search'):
            continue
        entries = model.objects.all()
        for entry in entries:
            entry.update_search()


if __name__ == '__main__':
    import sys
    argv = len(sys.argv) > 1 and sys.argv[1] or None
    update(argv)
