# -*- coding: utf-8 -*-
"""
    inyoka.wiki.utils
    ~~~~~~~~~~~~~~~~~

    Contains various helper functions for the wiki.  Most of them are only
    usefor for the the wiki application itself, but there are use cases for
    some of them outside of the wiki too.  Any example for that is the diff
    renderer which might be useful for the pastebin too.


    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
import os
import re
import shutil
import urllib
from subprocess import Popen, PIPE
from cStringIO import StringIO
from tempfile import TemporaryFile
from sha import new as sha1
from itertools import ifilter
from werkzeug.utils import url_quote
from inyoka.conf import settings
from inyoka.wiki.storage import storage
from inyoka.utils.urls import href, is_external_target
from inyoka.portal.user import User



def has_conflicts(text):
    """Returns `True` if there are conflict markers in the text."""
    from inyoka.wiki.parser import parse, nodes
    if isinstance(text, basestring):
        text = parse(text)
    return text.query.all.by_type(nodes.ConflictMarker).has_any


def debug_repr(obj):
    """
    A function that does a debug repr for an object.  This is used by all the
    `nodes`, `macros` and `parsers` so that we get a debuggable ast.
    """
    return '%s.%s(%s)' % (
        obj.__class__.__module__.rsplit('.', 1)[-1],
        obj.__class__.__name__,
        ', '.join('%s=%r' % (key, value)
        for key, value in sorted(getattr(obj, '__dict__', {}).items())
        if not key.startswith('_'))
    )


def simple_match(pattern, string, case_sensitive=False):
    """
    Match a string against a pattern.  Works like `simple_filter`.
    """
    return re.compile('^%s$%s' % (
        re.escape(pattern).replace('\\*', '.*?'),
        not case_sensitive and '(?i)' or ''
    )).match(string) is not None


def simple_filter(pattern, iterable, case_sensitive=True):
    """
    Filter an iterable against a pattern.  The pattern is pretty simple, the
    only special thing is that "*" is a wildcard.  The return value is an
    iterator, not a list.
    """
    return ifilter(re.compile('^%s$%s' % (
        re.escape(pattern).replace('\\*', '.*?'),
        not case_sensitive and '(?i)' or ''
    )).match, iterable)


def dump_argstring(argdef, sep=u', '):
    """Create an argument string from an argdef list."""
    result = []
    for is_kwarg, is_default, name, typedef, value in argdef:
        if is_default:
            continue
        if typedef is bool:
            value = value and 'ja' or 'nein'
        result.append((is_kwarg and name + '=' or '') + value)
    return sep.join(result)


def get_smilies(full=False):
    """
    This method returns a list of tuples for all the smilies in the storage.
    Per default for multiple codes only the first one is returend, if you want
    all codes set the full parameter to `True`.
    """
    if full:
        return storage.smilies[:]
    result = []
    images_yielded = set()
    for code, img in storage.smilies:
        if img in images_yielded:
            continue
        result.append((code, img))
        images_yielded.add(img)
    return result


def resolve_interwiki_link(wiki, page):
    """
    Resolve an interwiki link. If no such wiki exists the return value
    will be `None`.
    """
    if wiki == 'user':
        return href('portal', 'user', page)
    if wiki == 'attachment':
        return href('wiki', '_attachment', target=page)
    rule = storage.interwiki.get(wiki)
    if rule is None:
        return
    quoted_page = url_quote(page, safe='%')
    if '$PAGE' not in rule:
        link = rule + page
    else:
        link = rule.replace('$PAGE', page)
    return link


def get_thumbnail(location, width=None, height=None, force=False):
    """
    This function generates a thumbnail for an uploaded image or external one.
    It uses the media root to cache those thumbnails.  A script should delete
    thumbnails once a month to get rid of unused thumbnails.  The wiki will
    recreate thumbnails automatically.

    The return value is `None` if it cannot generate a thumbnail or the path
    for the thumbnail.  Join it with the media root or media URL to get the
    internal filename or external url.  This method either generates a PNG or
    JPG thumbnail.  It tries both and uses the smaller file.
    """
    if not width and not height:
        raise ValueError('neither with nor height given')
    if is_external_target(location):
        external = True
        if isinstance(location, unicode):
            location = location.encode('utf-8')
        partial_hash = sha1(location).hexdigest()
    else:
        from inyoka.wiki.models import Page
        page_filename = Page.objects.attachment_for_page(location)
        if page_filename is None:
            return
        partial_hash = sha1(page_filename).hexdigest()
        external = False

    dimension = '%sx%s%s' % (
        width and int(width) or '',
        height and int(height) or '',
        force and '!' or ''
    )
    hash = '%s%s%s' % (
        partial_hash,
        external and 'e' or 'i',
        dimension.replace('!', 'f')
    )
    base_filename = os.path.join('wiki', 'thumbnails', hash[:1],
                                 hash[:2], hash)
    filenames = [base_filename + '.png', base_filename + '.jpeg']

    # check if we already have a thumbnail for this hash
    for fn in filenames:
        if os.path.exists(os.path.join(settings.MEDIA_ROOT, fn)):
            return fn

    # get the source stream. if the location is an url we load it using
    # the urllib and convert it into a StringIO so that we can fetch the
    # data multiple times. If we are operating on a wiki page we load the
    # most recent revision and get the attachment as stream.
    if external:
        try:
            src = StringIO(urllib.urlopen(location).read())
        except IOError:
            return
    else:
        src = file(os.path.join(settings.MEDIA_ROOT, page_filename), 'rb')


    # convert into the PNG and JPEG using imagemagick. Right now this
    # rethumbnails for every format. This should be improved that it
    # generates the thumbnail first into a raw format and convert to
    # png/jpeg from there.
    base_params = [os.path.join(settings.IMAGEMAGICK_PATH, 'convert'),
                   '-', '-resize', dimension, '-sharpen', '0.5', '-format']

    results = []
    try:
        for format, quality in ('png', '100'), ('jpeg', '80'):
            dst = TemporaryFile()
            client = Popen(base_params + [format, '-quality', quality, '-'],
                           stdin=PIPE, stdout=dst, stderr=PIPE)
            src.seek(0)
            shutil.copyfileobj(src, client.stdin)
            client.stdin.close()
            client.stderr.close()
            if client.wait():
                return
            dst.seek(0, 2)
            pos = dst.tell()
            results.append((pos, dst, format))
    finally:
        src.close()

    # select the smaller of the two versions and copy and get the filename for
    # that format. Then ensure that the target folder exists
    results.sort()
    pos, fp, extension = results[0]
    filename = '%s.%s' % (
        base_filename,
        extension
    )
    real_filename = os.path.join(settings.MEDIA_ROOT, filename)
    try:
        os.makedirs(os.path.dirname(real_filename))
    except OSError:
        pass

    # rewind the descriptor and copy the data over to the target filename.
    fp.seek(0)
    f = file(real_filename, 'wb')
    try:
        shutil.copyfileobj(fp, f)
    finally:
        fp.close()
        f.close()

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
    snapshot_folders = set()
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


def quote_text(text, author=None):
    """
    Returns the wiki syntax quoted version of `text`.
    If the optional argument `author` (username as string or User object) is
    given, a written-by info is prepended.
    """
    if isinstance(author, User):
        author = author.username
    by = author and (u"[user:%s:] schrieb:\n" % author) or u''
    return text and by + u'\n'.join(
        '>' + (not line.startswith('>') and ' ' or '') + line
        for line in text.split('\n')
    ) or u''


class ArgumentCollector(type):
    """
    Metaclass for classes that accept arguments.
    """

    def __new__(cls, name, bases, d):
        no_parser = d.get('has_argument_parser')
        if not no_parser:
            for base in bases:
                if getattr(base, 'has_argument_parser', False):
                    no_parser = True
        if no_parser:
            return type.__new__(cls, name, bases, d)
        arguments = d.get('arguments', ())
        old_init = d.get('__init__')

        def new_init(self, *args, **orig_kw):
            if orig_kw.pop('_raw', False) and old_init:
                return old_init(self, *args, **orig_kw)
            missing = object()
            result, args, kwargs = args[:-2], args[-2], args[-1]
            result = list(result)
            argdef = []
            for idx, (key, typedef, default) in enumerate(arguments):
                try:
                    value = args[idx]
                    kwarg = False
                except IndexError:
                    value = kwargs.get(key, missing)
                    kwarg = True
                if value is missing:
                    value = default
                    is_default = True
                else:
                    is_default = False
                    if typedef in (int, float, unicode):
                        try:
                            value = typedef(value)
                        except:
                            value = default
                    elif typedef is bool:
                        value = value.lower() in ('ja', 'wahr', 'positiv', '1')
                    elif isinstance(typedef, tuple):
                        if value not in typedef:
                            value = default
                    elif isinstance(typedef, dict):
                        value = typedef.get(value, default)
                    else:
                        assert 0, 'invalid typedef'
                result.append(value)
                argdef.append((kwarg, is_default, key, typedef, value))
            self.argument_def = argdef
            if old_init:
                old_init(self, *result, **orig_kw)

        if old_init:
            new_init.__doc__ = old_init.__doc__
            new_init.__module__ = old_init.__module__
        d['__init__'] = new_init
        return type.__new__(cls, name, bases, d)
