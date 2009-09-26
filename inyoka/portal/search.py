# -*- coding: utf-8 -*-
"""
    inyoka.portal.search
    ~~~~~~~~~~~~~~~~~~~~

    Since the portal doesn't create and store searchable documents by its
    own this module only provides some general customations which are
    available through the whole portal.  For the concrete implementations
    have a look at the `inyoka.app.search` modules, where app is the
    name of the application.

    :copyright: Copyright 2007 by Christoph Hack.
    :license: GNU GPL.
"""
# THIS MODULE IS A STUB
# WE NEED IT FOR NOW CAUSE OF IMPORT ERRORS
import xapian
from inyoka.portal.user import User
from inyoka.utils.search import search_handler
