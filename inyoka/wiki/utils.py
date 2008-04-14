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
import difflib
import heapq
import posixpath
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
from inyoka.utils.urls import href
from inyoka.utils.html import escape


_path_crop = re.compile(r'^(..?/)+')
_unsupported_re = re.compile(r'[\x00-\x19#%?]+')
_schema_re = re.compile(r'[a-z]+://')


def has_conflicts(text):
    """Returns `True` if there are conflict markers in the text."""
    from inyoka.wiki.parser import parse, nodes
    if isinstance(text, basestring):
        text = parse(text)
    return text.query.all.by_type(nodes.ConflictMarker).has_any


def pagename_join(name1, name2):
    """
    Join a page with another one.  This works similar to a normal filesystem
    path join but with different rules.  Here some examples:

    >>> pagename_join('Foo', 'Bar')
    'Foo/Bar'
    >>> pagename_join('Foo', '/Bar')
    'Bar'
    >>> pagename_join('Foo', 'Bar/Baz')
    'Bar/Baz'
    >>> pagename_join('Foo', './Bar/Baz')
    'Foo/Bar/Baz'
    """
    if '/' in name2 and not _path_crop.match(name2):
        name2 = '/' + name2
    path = posixpath.join(name1, name2).lstrip('/')
    return _path_crop.sub('', posixpath.normpath(path))


def normalize_pagename(name, strip_location_markers=True):
    """
    Normalize a pagename.  Strip unsupported characters.  You have to call
    this function whenever you get a pagename from user input.  The models
    itself never check for normalized names and passing unnormalized page
    names to the models can cause serious breakage.

    If the second parameter is set to `False` the leading slashes or slash
    like path location markers are not removed.  That way the pagename is
    left unnormalized to a part but will be fully normalized after a
    `pagename_join` call.
    """
    name = u'_'.join(_unsupported_re.sub('', name).split()).rstrip('/')
    if not strip_location_markers:
        return name
    if name.startswith('./'):
        return name[2:]
    elif name.startswith('../'):
        return name[3:]
    return name.lstrip('/')


def is_external_target(location):
    """
    Check if a target points to an external URL or an internal page.  Returns
    `True` if the target is an external URL.
    """
    return _schema_re.match(location) is not None


def get_title(name, full=True):
    """
    Get the title for a page by name.  Per default it just returns the title
    for the full page, not just the last part.  If you just want the part
    after the last slash set `full` to `False`.
    """
    name = normalize_pagename(name)
    if not full:
        name = name.rsplit('/', 1)[-1]
    return u' '.join(x for x in name.split('_') if x)


def get_close_matches(name, matches, n=10, cutoff=0.6):
    """
    This is a replacement for a function in the difflib with the same name.
    The difference between the two implementations is that this one is case
    insensitive and optimized for page names.
    """
    s = difflib.SequenceMatcher()
    s.set_seq2(name.lower())
    result = []
    for name in matches:
        s.set_seq1(name.lower())
        if s.real_quick_ratio() >= cutoff and \
           s.quick_ratio() >= cutoff and \
           s.ratio() >= cutoff:
            result.append((s.ratio(), name))
    return heapq.nlargest(n, result)


def debug_repr(obj):
    """
    A function that does a debug repr for an object.  This is used by all the
    `nodes`, `macros` and `parsers` so that we get a debuggable ast.
    """
    return '%s.%s(%s)' % (
        obj.__class__.__module__.rsplit('.', 1)[-1],
        obj.__class__.__name__,
        ', '.join('%s=%r' % (key, value)
        for key, value in sorted(getattr(obj, '__dict__', {}).items()))
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
    Resolve an interwiki link.  If no such wiki exists the return value
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
    if '$PAGE' not in page:
        link = rule + page
    else:
        link = rule.replace('$PAGE', page)
    return link


def generate_udiff(old, new, old_title='', new_title='',
                   context_lines=4):
    """
    Generate an udiff out of two texts.  If titles are given they will be
    used on the diff.  `context_lines` defaults to 5 and represents the
    number of lines used in an udiff around a changed line.
    """
    return u'\n'.join(difflib.unified_diff(
        old.splitlines(),
        new.splitlines(),
        fromfile=old_title,
        tofile=new_title,
        lineterm='',
        n=context_lines
    ))


def prepare_udiff(udiff):
    """
    Prepare an udiff for the template.  The `Diff` model uses this to render
    an udiff into a HTML table.
    """
    return DiffRenderer(udiff).prepare()


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
    If the optional argument `author` is given, a written-by info is
    prepended.
    """
    by = author and (u"[user:%s:] schrieb:\n" % author.username) or u''
    return by + u'\n'.join(
        '>' + (not line.startswith('>') and ' ' or '') + line
        for line in text.split('\n')
    )


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


class DiffRenderer(object):
    """
    Give it a unified diff and it returns a list of the files that were
    mentioned in the diff together with a dict of meta information that
    can be used to render it in a HTML template.
    """
    _chunk_re = re.compile(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')

    def __init__(self, udiff):
        """
        :param udiff:   a text in udiff format
        """
        self.lines = [escape(line) for line in udiff.splitlines()]

    def _extract_rev(self, line1, line2):
        """Extract the filename and revision hint from a line."""
        try:
            if line1.startswith('--- ') and line2.startswith('+++ '):
                filename, old_rev = line1[4:].split(None, 1)
                new_rev = line2[4:].split(None, 1)[1]
                return filename, 'Alt', 'Neu'
        except (ValueError, IndexError):
            pass
        return None, None, None

    def _highlight_line(self, line, next):
        """Highlight inline changes in both lines."""
        start = 0
        limit = min(len(line['line']), len(next['line']))
        while start < limit and line['line'][start] == next['line'][start]:
            start += 1
        end = -1
        limit -= start
        while -end <= limit and line['line'][end] == next['line'][end]:
            end -= 1
        end += 1
        if start or end:
            def do(l):
                last = end + len(l['line'])
                if l['action'] == 'add':
                    tag = 'ins'
                else:
                    tag = 'del'
                l['line'] = u'%s<%s>%s</%s>%s' % (
                    l['line'][:start],
                    tag,
                    l['line'][start:last],
                    tag,
                    l['line'][last:]
                )
            do(line)
            do(next)

    def _parse_udiff(self):
        """Parse the diff an return data for the template."""
        lineiter = iter(self.lines)
        files = []
        try:
            line = lineiter.next()
            while True:
                # continue until we found the old file
                if not line.startswith('--- '):
                    line = lineiter.next()
                    continue

                chunks = []
                filename, old_rev, new_rev = \
                    self._extract_rev(line, lineiter.next())
                files.append({
                    'filename':         filename,
                    'old_revision':     old_rev,
                    'new_revision':     new_rev,
                    'chunks':           chunks
                })

                line = lineiter.next()
                while line:
                    match = self._chunk_re.match(line)
                    if not match:
                        break

                    lines = []
                    chunks.append(lines)

                    old_line, old_end, new_line, new_end = \
                        [int(x or 1) for x in match.groups()]
                    old_line -= 1
                    new_line -= 1
                    old_end += old_line
                    new_end += new_line
                    line = lineiter.next()

                    while old_line < old_end or new_line < new_end:
                        if line:
                            command, line = line[0], line[1:]
                        else:
                            command = ' '
                        affects_old = affects_new = False

                        if command == ' ':
                            affects_old = affects_new = True
                            action = 'unmod'
                        elif command == '+':
                            affects_new = True
                            action = 'add'
                        elif command == '-':
                            affects_old = True
                            action = 'del'
                        else:
                            raise RuntimeError()

                        old_line += affects_old
                        new_line += affects_new
                        lines.append({
                            'old_lineno':   affects_old and old_line or u'',
                            'new_lineno':   affects_new and new_line or u'',
                            'action':       action,
                            'line':         line
                        })
                        line = lineiter.next()

        except StopIteration:
            pass

        # highlight inline changes
        for file in files:
            for chunk in chunks:
                lineiter = iter(chunk)
                first = True
                try:
                    while True:
                        line = lineiter.next()
                        if line['action'] != 'unmod':
                            nextline = lineiter.next()
                            if nextline['action'] == 'unmod' or \
                               nextline['action'] == line['action']:
                                continue
                            self._highlight_line(line, nextline)
                except StopIteration:
                    pass

        return files

    def prepare(self):
        """Prepare the passed udiff for HTML rendering."""
        return self._parse_udiff()
