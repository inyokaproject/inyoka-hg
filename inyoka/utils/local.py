# -*- coding: utf-8 -*-
"""
    inyoka.utils.local
    ~~~~~~~~~~~~~~~~~~

    All kinds of request local magic.  This module provides two objects:

    `local`
        a werkzeug local object bound to the current request.

    `current_request`
        A proxy to the current active request object.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from inyoka.middlewares.common import local
current_request = local('request')
