# -*- coding: utf-8 -*-
"""
    inyoka.utils.imaging
    ~~~~~~~~~~~~~~~~~~~~

    This module implements some helper methods to generate thumbnails

    :copyright: 2010 by the Project Name Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os
from hashlib import sha1
from contextlib import closing
from PIL import Image
from inyoka.conf import settings


def _get_box(width, height):
    if width and height:
        return (int(width), int(height))
    elif width and not height:
        return (int(width), int(width))
    elif height and not width:
        return (int(height), int(height))


def get_thumbnail(location, destination, width=None, height=None, force=False):
    """
    This function generates a thumbnail for an uploaded image.
    It uses the media root to cache those thumbnails.  A script should delete
    thumbnails once a month to get rid of unused thumbnails.  The wiki will
    recreate thumbnails automatically.

    The return value is `None` if it cannot generate a thumbnail or the path
    for the thumbnail.  Join it with the media root or media URL to get the
    internal filename.  This method generates a PNG thumbnail.
    """
    if not width and not height:
        raise ValueError('neither with nor height given')

    fn = os.path.join(settings.MEDIA_ROOT, destination + '.png')
    if os.path.exists(fn):
        return destination + '.png'

    # get the source stream. if the location is an url we load it using
    # the urllib2 and convert it into a StringIO so that we can fetch the
    # data multiple times. If we are operating on a wiki page we load the
    # most recent revision and get the attachment as stream.
    try:
        src = open(os.path.join(settings.MEDIA_ROOT, location), 'rb')
    except IOError:
        return

    result = []
    format, quality = ('png', '100')
    with closing(src) as src:
        img = Image.open(src)
        img.thumbnail(_get_box(width, height), Image.ANTIALIAS)
        filename = '%s.%s' % (destination, format)
        real_filename = os.path.join(settings.MEDIA_ROOT, filename)
        try:
            os.makedirs(os.path.dirname(real_filename))
        except OSError:
            pass
        img.save(real_filename, quality=100)

    # Return none if there were errors in thumbnail rendering, that way we can
    # raise 404 exceptions instead of raising 500 exceptions for the user.
    return filename


def clean_thumbnail_cache():
    """
    This should be called by a cron about once a week.  It automatically
    deletes external thumbnails (so that they expire over a time) and not
    referenced internal attachments (for example old revisions).

    It returns the list of deleted files *and* directories.  Keep in mind
    that the return value is more or less useless except for statistics
    because in the meantime something could have recreated a directory or
    even a file.
    """
    from inyoka.wiki.models import Page
    attachments = {}
    for page in Page.objects.iterator():
        latest_rev = page.revisions.latest()
        if latest_rev.attachment:
            filename = latest_rev.attachment.file
            # the utf-8 encoding is fishy. as long as django leaves it
            # undefined what it does with the filenames it's the best
            # we can do.
            hash = sha1(filename.encode('utf-8')).hexdigest()
            attachments[hash] = filename

    # get a snapshot of the files and folders when we start executing. This
    # is important because someone could change the files while we operate
    # on them
    thumb_folder = os.path.join(settings.MEDIA_ROOT, 'wiki', 'thumbnails')
    snapshot_filenames = set()
    for dirpath, dirnames, filenames in os.walk(thumb_folder):
        dirpath = os.path.join(thumb_folder, dirpath)
        for filename in filenames:
            snapshot_filenames.add(os.path.join(dirpath, filename))

    to_delete = set()
    for filename in snapshot_filenames:
        basename = os.path.basename(filename)
        # something odd ended up there or the file was external.
        # delete it now.
        if len(basename) < 41 or basename[40] == 'e':
            to_delete.add(filename)
        else:
            hash = basename[:40]
            if hash not in attachments:
                to_delete.add(filename)

    # now delete all the collected files.
    probably_empty_dirs = set()
    deleted = []
    for filename in to_delete:
        try:
            os.remove(filename)
        except (OSError, IOError):
            continue
        probably_empty_dirs.add(os.path.dirname(filename))
        deleted.append(filename)

    # maybe we can get rid of some directories. try that
    for dirname in probably_empty_dirs:
        try:
            os.rmdir(dirname)
        except OSError:
            continue
        deleted.append(dirname)

    return deleted


