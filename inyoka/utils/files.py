# -*- coding: utf-8 -*-
"""
    inyoka.utils.files
    ~~~~~~~~~~~~~~~~~~

    File related utilities.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""

import mimetypes

def fix_extension(filename, mime):
    """Adds a proper extension according to the mimetype"""
    possible_extensions = mimetypes.guess_all_extensions(mime)
    if not possible_extensions:
        return filename
    if '.' + filename.rsplit('.', 1)[-1].lower() not in possible_extensions:
        # .jpe is an ugly extension for jpeg, use .jpg
        ext = '.jpg' if mime=='image/jpeg' else mimetypes.guess_extension(mime)
        return filename.rsplit('.', 1)[0] + ext
