#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.clean_temp_dirs
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Clean up temporary directories.

    :copyright: Copyright 2009 by Marian Sigler.
    :license: GNU GPL.
"""

import sys
from subprocess import call
from inyoka.conf import settings

error = False

# If a user uploads an attachment and then cancels posting the attachment is 
# not deleted.
ret = call(['find', 'forum/attachments/temp/', '-ctime', '+1', '-exec', 'rm', '{}', ';'],
          cwd=settings.MEDIA_ROOT, stdout=sys.stdout, stderr=sys.stderr)
if ret:
    print >> sys.stderr, 'Error while deleting temporary forum attachments: find exited with status code %d' % ret
    error = True


if error:
    sys.exit(1)
