# -*- coding: utf-8 -*-
"""
    inyoka.portal.search
    ~~~~~~~~~~~~~~~~~~~~

    Since the portal doesn't create and store searchable documents by its
    own this module only provides some general customations which are
    available through the whole portal.  For the concrete implementations
    have a look at the `inyoka.app.search` modules, where app is the
    name of the application.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
# THIS MODULE IS A STUB
# WE NEED IT FOR NOW CAUSE OF IMPORT ERRORS
import xapian
from inyoka.portal.user import User
from inyoka.utils.search import search_handler
