# -*- coding: utf-8 -*-
"""
    inyoka.utils.local
    ~~~~~~~~~~~~~~~~~~

    All kinds of request local magic.  This module provides two objects:

    `local`
        a werkzeug local object bound to the current request.

    `current_request`
        A proxy to the current active request object.

    The purpose of this module is to allow functions to access request data
    in the context of a request without explicitly passing the request object.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
from werkzeug import Local, LocalManager

local = Local()
local_manager = LocalManager(local)
current_request = local('request')
request_cache = local('cache')
