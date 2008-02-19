# -*- coding: utf-8 -*-
"""
    inyoka.wiki.models
    ~~~~~~~~~~~~~~~~~~

    This module implements the database models for the wiki.  It's important
    to know that this doesn't automatically mean that an operation hits the
    database.  In fact most operations will happen either on the caching
    system or the python layer.  Operations that hit the database are all
    native django query methods (which are left untouched) and those that
    are documented to do so.

    This module implements far more models that are acutually in use in the
    `actions`.  This is because the `Page` model and the `PageManager` also
    manage other models such as `Revision`, `Text` and of course also the
    special `Attachment` model which in fact never leaves the module except
    for read only access.

    For details about manipulating and querying objects check out the
    `PageManager` documentation as well as the `Page` documentation.  If you
    just want infos about the models as such that are passed to the template
    context see `Page`, `Attachment`, `Revision`, `Text` and `Diff`.


    Meta Data
    =========

    Meta data keys starting with an capital X, followed by an dash are used
    internally.  Some of them have a special meaning, others are ignored by
    the software until they get a meaning by code updates.

    The following keys are currently in use:

    ``X-Link``
        For every internal link in the page an ``X-Link`` is emitted.  This is
        used by the wiki system to look up backlinks, invalidate caches,
        find missing pages or orphans etc.  Links that leave the parser are
        considered "implicitly relative" which means that they are always
        joined with the current page name.  If a parser wants to avoid that
        it must prefix it with an slash before emitting it.

    ``X-Attach``
        Works like ``X-Link`` but this is emitted if a page is included with
        a macro that displays a page inline.  Examples are the `Picture` or
        the `Include` macro.  This is also considered being an "implicit
        relative" reference thus if something just accepts an absolute link
        this must prefix it with an slash.

    ``X-Redirect``
        Marks this page as redirect to another page.  This should be an
        absolute link to an existing page.

    ``X-Behave``
        Gives the page a behavior.  This is used by the `storage` system and
        documented as part of that module.

    ``X-Cache-Time``
        This is used to give the page a different cache time than the default.

    ``X-Owner``
        Every user or group (prefixed with an ``'@'``) defined this way is
        added to the special ACL ``@Owner`` group.  This is for example used
        for user wiki pages that should only give moderators, administrators
        and the owner of the page access.

    Every internal key is only modifyable by people with the ``PRIV_MANAGE``
    privilege.  Some keys like `X-Link` and `X-Attach` that are defined also
    by the wiki parser itself are marked as `LENIENT_METADATA_KEYS` which
    gives users without the `PRIV_MANAGE` privlege to edit them.

    Apart of those users without this privilege will see the metadata in their
    editor but if they try to send changed metadata back to the database the
    wiki will avoid that.  The models itself do not test for changed metadata
    that is part of the `acl` system.


    :copyright: Copyright 2007 by Armin Ronacher, Benjamin Wiegand.
    :license: GNU GPL.
"""
import sha
from math import log
from datetime import datetime
from mimetypes import guess_type
from django.db import models, connection
from django.conf import settings
from django.core.cache import cache
from django.utils.html import escape
from inyoka.wiki.utils import generate_udiff, prepare_udiff, \
     get_close_matches, get_title, pagename_join
from inyoka.wiki import parser, templates
from inyoka.wiki.storage import storage
from inyoka.utils import deferred
from inyoka.utils.dates import format_specific_datetime, format_datetime
from inyoka.utils.urls import href
from inyoka.utils.search import search
from inyoka.utils.highlight import highlight_code
from inyoka.utils.templating import render_template
from inyoka.utils.collections import MultiMap
from inyoka.middlewares.registry import r
from inyoka.forum.models import Topic
from inyoka.portal.user import User


class PageManager(models.Manager):
    """
    Because our table definitions are rather complex due to shared text,
    revisions etc the `PageManager` binds some of those attributes
    directly on the page object to give a simpler interface in templates.

    The `PageManager` singleton instance is available as `Page.objects`.
    """

    def exists(self, name):
        """Check if a page with that name exists."""
        return name in self.get_page_list()

    def get_head(self, name, offset=0):
        """
        Return the revision ID for head or with an offset.  The offset
        can be an negative or positive number, but despite that always
        the absolute number is used.  This is useful if you want the non
        head revision, say to compare head with head - 1 you can call
        ``Page.objects.get_head("Page_Name", -1)``.
        """
        cur = connection.cursor()
        cur.execute('''
            select r.id
              from wiki_revision r, wiki_page p
             where p.name = %s and p.id = r.page_id
          order by r.id desc
             limit 1, %s;
        ''', [name, abs(offset)])
        row = cur.fetchone()
        cur.close()
        if row:
            return row[0]

    def get_tagcloud(self, max=100):
        """
        Get a tagcloud.  Note that this is one of the few operations that
        also returns attachments, not only pages.  A tag cloud is represented
        as ordinary list of dicts with the following keys:

        ``'name'``
            The name of the tag

        ``'count'``
            Number of pages flagged with this tag.

        ``'size'``:
            The relative size of this page in percent.  One page means a size
            of 100%.  The number is calculated using the natural logarithm.
            In theory there is no upper limit for the tag size but it won't
            grow unnecessary high with a sane page count (< 1000000 pages)
        """
        cur = connection.cursor()
        cur.execute('''
            select w.value, count(w.value) as `count`
              from wiki_metadata w
             where w.key = 'tag'
          group by w.value
          order by `count` desc %s;
        ''' % (max is not None and 'limit %d' % max or ''))
        try:
            return [{
                'name':     tag[0],
                'count':    tag[1],
                'size':     round(100 + log(tag[1] or 1) * 20, 2)
            } for tag in sorted(cur.fetchall(), key=lambda x: x[0].lower())]
        finally:
            cur.close()

    def compare(self, name, old_rev, new_rev=None):
        """
        Compare two revisions of a page.  If the new revision is not given,
        the most recent one is taken.  The return value of this operation
        is a `Diff` instance.
        """
        if new_rev is not None:
            new_rev = int(new_rev)
        old_page = self.get_by_name_and_rev(name, int(old_rev))
        new_page = self.get_by_name_and_rev(name, new_rev)
        return Diff(old_page, old_page.rev, new_page.rev)

    def _get_object_list(self, nocache):
        """
        Get a list of all objects that are pages or attachments.  The return
        value is a list of ``(name, deleted, latest_rev, is_page)`` tuples
        where `is_page` is False if that object is an attachment.
        """
        key = 'wiki/object_list'
        pagelist = None
        if not nocache:
            pagelist = cache.get(key)

        if pagelist is None:
            cur = connection.cursor()
            cur.execute('''
                select p.name, r.deleted, r.id, r.attachment_id is null
                  from wiki_page p, wiki_revision r
                 where p.id = r.page_id and r.id = (
                 select max(id) from wiki_revision
                 where page_id = p.id)
                 order by p.name
            ''')
            pagelist = cur.fetchall()
            cur.close()
            # we cache that also if the user wants something uncached
            # because if we are already fetching it we can cache it.
            cache.set(key, pagelist, 10000)
        return pagelist

    def get_page_list(self, existing_only=True, nocache=False):
        """
        Get a list of unicode strings with the page names that have a
        head that exists.  Normally the results are cached, pass it
        `nocache` if you want to force the database query.  Normally this
        is not necessary because whenever a page is deleted or created the
        pagelist cache is invalidated.
        """
        return [x[0] for x in self._get_object_list(nocache)
                if not existing_only or not x[1] and x[3]]

    def get_attachment_list(self, parent=None, existing_only=True,
                            nocache=False):
        """
        Works like `get_page_list` but just lists attachments.  If parent is
        given only pages blow that page are displayed.
        """
        filtered = (x[0] for x in self._get_object_list(nocache)
                    if not existing_only or not x[1] and not x[3])
        if parent is not None:
            parent += u'/'
            filtered = (x for x in filtered if x.startswith(parent))
        return list(filtered)

    def get_page_count(self, existing_only=True, nocache=False):
        """
        Get the number of pages.  Per default just pages with an non
        deleted head will be returned.  This in fact just counts the
        results returned by `get_page_list` because we hit the cache most
        of the time anyway.
        """
        return len(self.get_page_list(existing_only, nocache))

    def get_attachment_count(self, existing_only=True, nocache=False):
        """Get the number of attachments."""
        return len(self.get_attachment_list(existing_only, nocache))

    def get_owners(self, page_name):
        """
        Get a set of owners defined using the ``'X-Owner'`` metadata key.
        This set may include groups too and is probably just seful for the
        `get_privilege_flags` function from the `acl` module which uses it.

        Groups are prefixed with an ``'@'`` sig.-
        """
        cursor = connection.cursor()
        cursor.execute('''
            select m.value from wiki_metadata m, wiki_page p
             where m.key = 'X-Owner' and m.page_id = p.id and
                   p.name = %s;
        ''', [page_name])
        try:
            return set(x[0] for x in cursor.fetchall())
        finally:
            cursor.close()

    def get_owned(self, owners):
        """
        Return all the pages a user or some group (prefixed with ``@`` own).
        The return value will be a list of page names, not page objects.

        Reverse method of `get_owners`.
        """
        cursor = connection.cursor()
        cursor.execute('''
            select p.name from wiki_metadata m, wiki_page p
             where m.key = 'X-Owner' and m.page_id = p.id and
                   m.value in (%s);
        ''' % ', '.join(['%s'] * len(owners)), list(owners))
        try:
            return set(x[0] for x in cursor.fetchall())
        finally:
            cursor.close()

    def get_orphans(self):
        """
        Return a list of orphaned pages.  The return value will be a list
        of unicode strings, not the actual page object.  This ignores
        attachments!
        """
        ignore = set([settings.WIKI_MAIN_PAGE])
        cur = connection.cursor()
        cur.execute('''
            select p.name, r.id
              from wiki_page p, wiki_revision r
             where r.attachment_id is null and not exists (
                select *
                  from wiki_metadata m
                 where p.name = m.value and m.key = 'X-Link'
             ) and r.page_id = p.id and r.id = (select max(id)
               from wiki_revision where page_id = r.page_id)
          order by p.name
        ''')
        try:
            return [x[0] for x in cur.fetchall() if x[0] not in ignore]
        finally:
            cur.close()

    def get_missing(self):
        """
        Return a list of referenced page names that do not have existing
        pages.
        """
        cur = connection.cursor()
        # FIXME: this query is hideous and probably the worst way to
        # achieve that. Fix that!
        cur.execute('''
            select m.value
              from wiki_metadata m
             where m.key = 'X-Link' and m.value not in (
                select s.name from (
                    select p.name, max(r.id)
                      from wiki_page p, wiki_revision r
                     where r.attachment_id is null and
                           p.id = r.id and not r.deleted
                  group by r.id
                ) as s
             )
          order by m.value
        ''')
        try:
            return [x[0] for x in cur.fetchall()]
        finally:
            cur.close()

    def get_similar(self, name, n=10):
        """
        Pass it a name and it will give you a list of page names with a
        similar name.  This also checks for similar attachments.
        """
        return [x[1] for x in get_close_matches(name, [x[0] for x in
                self._get_object_list(False) if not x[1]], n)]

    def get_by_name(self, name, nocache=False, raise_on_deleted=False):
        """
        Return a page with the most recent revision.  This should be used
        from the view functions if no revision is defined because it sends
        just one query to get all data.

        The most recent version is additionally stored in the cache so that
        we don't hit the database for that.  Because some caching backends
        share cached objects you should not modify it unless you bypass
        the caching backend by passing `nocache` = True.
        """
        rev = None
        if not nocache:
            key = 'wiki/page/' + name
            rev = cache.get(key)
        if rev is None:
            try:
                rev = Revision.objects.select_related(depth=1) \
                                      .filter(page__name=name) \
                                      .latest()
            except Revision.DoesNotExist:
                raise Page.DoesNotExist()
        if not nocache:
            try:
                cachetime = int(rev.page.metadata['X-Cache-Time'][0]) or None
            except (IndexError, ValueError):
                cachetime = None
            cache.set(key, rev, cachetime)
        page = rev.page
        page.rev = rev
        if rev.deleted and raise_on_deleted:
            raise Page.DoesNotExist()
        return page

    def get_by_name_and_rev(self, name, rev, raise_on_deleted=False):
        """
        Works like `get_by_name` but selects a specific revision of a page,
        not the most recent one.  If `rev` is `None`, `get_by_name` is called.
        """
        if rev is None:
            return self.get_by_name(name, True, raise_on_deleted)
        rev = Revision.objects.select_related(depth=1).get(id=int(rev))
        if rev.page.name != name or (rev.deleted and raise_on_deleted):
            raise Page.DoesNotExist()
        rev.page.rev = rev
        return rev.page

    def find_by_metadata(self, key, value=None):
        """
        Return a list of pages that have an entry for key with value in their
        metadata section.
        """
        kwargs = {'key': key}
        if value is not None:
            kwargs['value'] = value
        rv = [x.page for x in MetaData.objects.select_related(depth=1).
              filter(**kwargs)]
        rv.sort(key=lambda x: x.name)
        return rv

    def find_by_tag(self, tag):
        """Return a list of page names tagged with `tag`."""
        cur = connection.cursor()
        cur.execute('''
            select p.name
              from wiki_page p, wiki_metadata m
             where m.key = 'tag' and m.value=%s and m.page_id = p.id;
        ''', (tag,))
        try:
            return [x[0] for x in cur.fetchall()]
        finally:
            cur.close()

    def attachment_for_page(self, page_name):
        """
        Get the internal filename of the attachment attached to the page
        provided.  If the page does not exist or it doesn't have an attachment
        defined the return value will be `None`.
        """
        cursor = connection.cursor()
        cursor.execute('''
            select a.file, max(r.id)
              from wiki_attachment a, wiki_revision r, wiki_page p
             where r.page_id = p.id and r.attachment_id = a.id and
                   p.name = %s and not r.deleted
          group by a.file;
        ''', [page_name])
        row = cursor.fetchone()
        if row:
            # XXX: right now django does not support any unicode character
            # in filenames. I believe however that this will change over time
            # so this goes the save way and encodes it to utf-8.
            return row[0].encode('utf-8')

    def get_recently_created(self, date):
        """
        Get the pages that were created after a special date.
        Returns a list of tuples containing the page name and the page
        creation date.
        """
        cur = connection.cursor()
        # XXX: I'm not able to make it working without a subquery. Maybe
        #      someone else is?
        cur.execute('''
            select p.name, r.change_date
             from wiki_revision r, wiki_page p
             where r.change_date > %s and
                   r.page_id = p.id and
                   r.id in (
                        select r.id
                         from wiki_revision r
                         group by r.page_id
                         order by r.change_date desc
                  )
        ''', [date])
        try:
            return [(x[0], x[1]) for x in cur.fetchall()]
        finally:
            cur.close()

    def create(self, name, text, user=None, change_date=None,
               note=None, attachment=None, attachment_filename=None,
               deleted=False, remote_addr=None, update_meta=True):
        """
        Create a new wiki page.  Always use this method to create pages,
        never the `Page` constructor which doesn't create the revision and
        text objects.

        :Parameters:

            name
                This must be a *normaliezd* version of the page name.  The
                default action dispatcher (`ikhaya.wiki.views.show_page`)
                automatically normalizes incoming page names so this is no
                issue from the web layer.  However shell scripts, converters,
                crons etc have to normalize this parameter themselves.

            text
                Either a text object or a text that represents the text.  If
                it's a string inyoka calculates a hash of it and tries to find
                a text with the same value in the database.

            user
                If this paramter is `None` the inoyka system user will be the
                author of the created revision.  Otherwise it can either be a
                User or an AnoymousUser object from the auth contrib module.

            change_date
                If this is not provided the current date is used.  Otherwise
                it should be an UTC timestamp in form of a `datetime.datetime`
                object.

            note
                The change note for the revision.  If not given it will be
                ``'Created'`` or something like that.

            attachment
                see `attachment_filename`

            attachmene
                if an attachment filename is given the page will act as an
                attachment.  The `attachment` must be a bytestring in current
                django versions, for performance reasons latter versions
                probably will support a file descriptor here.

            deleted
                If this is `True` the page is created as an deleted page.
                This operation doesn't make sense and creates suprising
                displays in the revision log if the `note` is not changed to
                something reasonable.

            remote_addr
                The remote address of the user that created this page.  If not
                given it will be ``'127.0.0.1'`` but never the remote addr of
                the active request object.  This decision was made so that no
                confusion comes up when creating page objects in the context
                of a request that are not affiliated with the user.
            update_meta
                This is a boolean that defines whether metadata should be
                updated or not. It's useful to disable this for converter
                scripts.
        """
        page = Page(name=name)
        if change_date is None:
            change_date = datetime.utcnow()
        if isinstance(text, basestring):
            text, created = Text.objects.get_or_create(value=text)
        if note is None:
            node = 'Erstellt'
        if attachment is not None:
            att = Attachment()
            att.save_file_file(attachment_filename, attachment)
            att.save()
            attachment = att
        if user is None:
            user = User.objects.get_system_user()
        elif user.is_anonymous:
            user = None
        if remote_addr is None:
            remote_addr = '127.0.0.1'
        page.save()
        page.rev = Revision(page=page, text=text, user=user,
                            change_date=change_date, note=note,
                            attachment=attachment, deleted=deleted,
                            remote_addr=remote_addr)
        page.rev.save()
        if update_meta:
            page.update_meta()
        return page


class TextManager(models.Manager):
    """
    Helper manager for the text table so that we can get texts by the
    hash of an object.  You should always use the `get_or_create`
    function to get or create a text.  Available as `Text.objects`.
    """

    def get_or_create(self, value):
        """
        Works like a normal `get_or_create` function, just that it takes the
        value as positional argument too and that it uses an hash to find the
        correct text, rather than a string based search.
        """
        # XXX: check for hash collisions?
        hash = sha.new(value.encode('utf-8')).hexdigest()
        return models.Manager.get_or_create(self, hash=hash, defaults={
            'value': value
        })


class Diff(object):
    """
    This class represents the results of a page comparison.  You can get
    useful instances of this class by using the ``compare_*`` functions on
    the `PageManager`.

    :IVariables:
        page
            The page for the old and new revision.

        old_rev
            A revision object that points to the left, not necessarily older
            revision.

        new_rev
            A revision object like for `old_rev`, but for the right and most
            likely newer revision.

        udiff
            The udiff of the diff as string.

        template_diff
            The diff in parsed form for the template.  This is mainly used by
            the ``'wiki/_diff.html'`` template which is automatically rendered
            if one calls the `render()` method on the instance.
    """

    def __init__(self, page, old, new):
        """
        This constructor exists maily for internal usage.  It's not supported
        to create `Diff` object yourself.
        """
        self.page = page
        self.old_rev = old
        self.new_rev = new
        self.udiff = generate_udiff(old.text.value, new.text.value,
                                    u'%s (%s)' % (
                                        page.name,
                                        format_datetime(old.change_date)
                                    ), u'%s (%s)' % (
                                        page.name,
                                        format_datetime(new.change_date)
                                    ))
        diff = prepare_udiff(self.udiff)
        self.template_diff = diff and diff[0] or {}

    def render(self):
        """
        Render the diff using the ``wiki/_diff.html`` template.  Have a look
        at the class' docstring for more detail.
        """
        return render_template('wiki/_diff.html', {'diff': self})

    def __unicode__(self):
        return self.render()

    def __repr__(self):
        return '<%s %r - %r>' % (
            self.__class__.__name__,
            self.old_rev,
            self.new_rev
        )


class Text(models.Model):
    """
    The text for a revision.  Keep in mind that text objects are shared among
    revisions so *never ever* edit a text object after it was created.

    Because of that some methods require an explicit page object being passed
    or a `RenderContext`.

    :IVariables:

        value
            The raw unicode value of the text.

        hash
            The internal unique hash for this text.
    """
    objects = TextManager()
    value = models.TextField()
    hash = models.CharField(max_length=40, unique=True)
    cached_formats = ['html']

    def parse(self, template_context=None):
        """
        Parse the markup into a tree.  This also expands template code if the
        template context provided is not None.
        """
        if template_context is not None:
            value = templates.process(self.value, template_context)
        else:
            value = self.value
        return parser.parse(value)

    def find_meta(self):
        """
        Return all sort of metadata that is available on this page.  This
        includes links, commented metadata and the simplified text.
        """
        tree = self.parse()
        links = []
        metadata = []

        def walk(node):
            for child in node.children:
                if child.is_container:
                    walk(child)
                if child.__class__ is nodes.InternalLink:
                    # the leading slash enforces an absolute link.
                    links.append('/' + child.page)
                elif child.__class__ is nodes.MetaData:
                    for value in child.values:
                        metadata.append((child.key, value))
        walk(tree)

        return {
            'links':        links,
            'metadata':     metadata,
            'text':         tree.text
        }

    def prune(self):
        """Clear the page cache."""
        for format in self.cached_formats:
            cache.delete('wiki/text/%d/%s' % (self.id, format))

    def render(self, request=None, page=None, format='html',
               context=None, template_context=None, nocache=False):
        """
        This renders the markup of the text as html or any other
        format supported.  Per default all formats are cached, if
        you don't want to cache one just pass it ``nocache=True``.

        If no request is given the current request is used.
        """
        if context is None:
            context = parser.RenderContext(request or r.request, page)
        if template_context is not None or nocache or self.id is None or \
           format not in self.cached_formats:
            return self.parse(template_context).render(context, format)
        key = 'wiki/text/%d/%s' % (self.id, format)
        instructions = cache.get(key)
        if instructions is None:
            instructions = self.parse().compile(format)
            cache.set(key, instructions)
        return parser.render(instructions, context)

    def __unicode__(self):
        return self.render()

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.id
        )


class Page(models.Model):
    """
    This represents one wiki page and optionally also a bound revision.
    `Page` instances exist both bound and unbound.  We refer to a bound page
    when a revision was attached to the page *and* the query documents that.

    Some queries might add a revision to the page object for reasons of
    optimization.  In that case the page appears to be bound.  In such a
    situation it's unsafe to call `save()` on the page object.

    Only save pages obtained by a `PageManager.get_by_name()` or
    `PageManager.get_by_name_and_rev()`!

    :IVariables:

        name
            The normalized name of the page.  This is guaranteed to be unique.

        topic
            A foreign key to the topic that belongs to this wiki page.

        rev
            If the page is bound this points to a `Revision` otherwise `None`.
    """
    objects = PageManager()
    name = models.CharField(max_length=200, unique=True)
    topic = models.ForeignKey(Topic, blank=True, null=True)

    #: this points to a revision if created with a query method
    #: that attaches revisions. Also creating a page object using
    #: the create() function binds the revision.
    rev = None

    @property
    def title(self):
        """
        The title of the page.  This is automatically generated from the page
        name and cannot be changed.  However future versions might support
        giving pages different titles by using the metadata system.
        """
        return get_title(self.name)

    @property
    def short_title(self):
        """
        Like `title` but just the short version of it.  Thus it returns the
        outermost part (after the last slash).  This is primarly used in the
        `do_show` action.
        """
        return get_title(self.name, full=False)

    @property
    def full_title(self):
        """Like `title` but returns the revision information too."""
        if self.rev is not None:
            return self.rev.title
        return self.title

    @property
    def trace(self):
        """The trace of pages to this page."""
        parts = get_title(self.name, full=True).split('/')
        return [u'/'.join(parts[:idx + 1]) for idx in xrange(len(parts))]

    @deferred
    def backlinks(self):
        """List of `Page` objects that link to this page."""
        return Page.objects.find_by_metadata('X-Link', self.name)

    @deferred
    def embedders(self):
        """List of `Page` objects that embbed this page as attachment."""
        return Page.objects.find_by_metadata('X-Attach', self.name)

    @deferred
    def links(self):
        """
        Internal wiki links on this page.  Because there could be links to
        non existing pages the list returned contains just the link targets
        in normalized format, not the page objects as such.
        """
        cur = connection.cursor()
        cur.execute('''
            select m.value
              from wiki_metadata m
             where m.page_id = %s and m.key = 'X-Link'
        ''', [self.id])
        try:
            return [x[0] for x in cur.fetchall()]
        finally:
            cur.close()

    @deferred
    def metadata(self):
        """
        Get the metadata from this page as `MultiMap`.  It's not possible to
        change metadata from the model because it's an aggregated value from
        multiple sources (explicit metadata, backlinks, macros etc.)
        """
        cur = connection.cursor()
        cur.execute('''
            select m.key, m.value
              from wiki_metadata m
             where m.page_id = %s
        ''', [self.id])
        try:
            return MultiMap(cur.fetchall())
        finally:
            cur.close()

    @property
    def is_main_page(self):
        """`True` if this is the main page."""
        return self.name == settings.WIKI_MAIN_PAGE

    def update_meta(self):
        """
        Update page metadata.  Crosslinks and the search index.  This method
        always operates on the most recent revision, never on the revision
        attached to the page.  If there is no revision in the database yet
        this method fails silently.

        Thus the page create method has to call this after the revision was
        saved manually.
        """
        try:
            rev = self.revisions.latest()
        except Revision.DoesNotExist:
            return
        meta = rev.text.find_meta()

        # regular metadata and links
        new_metadata = set(meta['metadata'])

        for key, value in new_metadata:
            if key == 'X-Behave':
                storage.clear_cache()
                break

        # add links as x-links
        new_metadata.update(('X-Link', link) for link in meta['links'])

        # make links and attachment targets absolute
        for t in list(new_metadata):
            key, value = t
            if key in ('X-Link', 'X-Attach'):
                if t in new_metadata:
                    new_metadata.remove(t)
                new_metadata.add((key, pagename_join(self.name, value)))

        cur = connection.cursor()
        cur.execute('''
            select m.id, m.key, m.value
              from wiki_metadata m
             where m.page_id = %s
        ''', [self.id])
        to_remove = []

        for id, key, value in cur.fetchall():
            item = (key, value)
            if item in new_metadata:
                new_metadata.remove(item)
            else:
                to_remove.append(id)

        if to_remove:
            cur.execute('''
                delete from wiki_metadata
                 where id in (%s)
            ''' % ', '.join(['%s'] * len(to_remove)), list(to_remove))
        cur.close()

        for key, value in new_metadata:
            MetaData(page=self, key=key, value=value).save()

        # searchindex
        search.queue('w', self.id)

    def prune(self):
        """Clear the page cache."""
        cache.delete('wiki/page/' + self.name)
        if self.rev:
            self.rev.text.prune()
        deferred.clear(self)

    def save(self, update_meta=True):
        """
        This not only saves the page but also a revision that is
        bound to the page object.  If you don't want to save the
        revision set it to `None` before calling `save()`.
        """
        if self.id is None:
            cache.delete('wiki/object_list')
        models.Model.save(self)
        cur = connection.cursor()
        # XXX: this should also delete the page text cache.  But for that
        # we have to look up the latest revisions and the text.
        cur.execute('''
            select distinct p.name
              from wiki_page p, wiki_metadata m
             where (m.key = 'X-Link' or m.key = 'X-Attach')
               and m.value = %s and m.page_id = p.id
        ''', [self.name])
        for row in cur.fetchall():
            cache.delete('wiki/page/' + row[0])
        cur.close()
        cache.delete('wiki/page/' + self.name)

        if self.rev is not None:
            self.rev.save()
        if update_meta:
            self.update_meta()

        deferred.clear(self)

    def delete(self):
        """
        This deletes the page.  In fact it does not delete the page but add a
        "deleted" revision.  You should never use this method directly, always
        use `edit()` with `delete` set to `True` to get user data into the
        revision log.

        This method exists mainly to automatically delete pages without further
        information, for example if you want a cronjob to prune data
        automatically.
        """
        rev = self.revisions.latest().edit(
            deleted=True,
            text=u'',
            file=None,
            note=u'Von System gelöscht'
        )

    def edit(self, text=None, user=None, change_date=None,
             note=u'', attachment=None, attachment_filename=None,
             deleted=None, remote_addr=None, update_meta=True):
        """
        This saves outstanding changes and creates a new revision which is
        then attached to the `rev` attribute.

        :Parameters:

            text
                Either a text object or a text that represents the text.  If
                it's a string inyoka calculates a hash of it and tries to find
                a text with the same value in the database.  If no text is
                provided the text from the last revision is used.

            user
                If this paramter is `None` the inoyka system user will be the
                author of the created revision.  Otherwise it can either be a
                User or an AnoymousUser object from the auth contrib module.

            change_date
                If this is not provided the current date is used.  Otherwise
                it should be an UTC timestamp in form of a `datetime.datetime`
                object.

            note
                The change note for the revision.  If not given it will be
                empty.

            attachment
                see `attachment_filename`

            attachmene
                if an attachment filename is given the page will act as an
                attachment.  The `attachment` must be a bytestring in current
                django versions, for performance reasons latter versions
                probably will support a file descriptor here.  If no
                attachment filename is given the page will either continue to
                be a page or attachment depending on the last revision.

            deleted
                If this is `True` the page is created as an deleted page.
                This operation doesn't make sense and creates suprising
                displays in the revision log if the `note` is not changed to
                something reasonable.

            remote_addr
                The remote address of the user that created this page.  If not
                given it will be ``'127.0.0.1'`` but never the remote addr of
                the active request object.  This decision was made so that no
                confusion comes up when creating page objects in the context
                of a request that are not affiliated with the user.
            update_meta
                This is a boolean that defines whether metadata should be
                updated or not. It's useful to disable this for converter
                scripts.
        """
        try:
            rev = self.revisions.latest()
        except Revision.DoesNotExist:
            rev = None
        if deleted is None:
            if rev:
                deleted = rev.deleted
            else:
                deleted = False
        if deleted:
            text = ''
        if text is None:
            text = rev and rev.text or u''
        if isinstance(text, basestring):
            text, created = Text.objects.get_or_create(value=text)
        if attachment_filename is None:
            attachment = rev and rev.attachment or None
        elif attachment is not None:
            att = Attachment()
            att.save_file_file(attachment_filename, attachment)
            att.save()
            attachment = att
        if user is None:
            user = User.objects.get_system_user()
        elif user.is_anonymous:
            user = None
        if change_date is None:
            change_date = datetime.utcnow()
        if remote_addr is None:
            remote_addr = '127.0.0.1'
        self.rev = Revision(page=self, text=text, user=user,
                            change_date=change_date, note=note,
                            attachment=attachment, deleted=deleted,
                            remote_addr=remote_addr)
        self.save(update_meta=update_meta)
        if (deleted and rev and not rev.deleted) or \
           (not deleted and rev and rev.deleted):
            cache.delete('wiki/object_list')

    def get_absolute_url(self, action=None):
        if action == 'edit':
            return href('wiki', self.name, action='edit')
        return href('wiki', self.name)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return '<%s %r%s>' % (
            self.__class__.__name__,
            self.name,
            self.rev and ' rev %r' % self.rev.id or ''
        )

    class Meta:
        ordering = ['name']


class Attachment(models.Model):
    """
    Revisions can have uploaded data associated, this table holds the
    mapping to the uploaded file on the file system.
    """
    file = models.FileField(upload_to='wiki/attachments/%S/%W')

    @property
    def size(self):
        """The size of the attachment in bytes."""
        return self.get_file_size()

    @property
    def filename(self):
        """The filename of the attachment on the filesystem."""
        return self.get_file_filename()

    @property
    def mimetype(self):
        """The mimetype of the attachment."""
        return guess_type(self.get_file_filename())[0] or \
               'application/octet-stream'

    @property
    def contents(self):
        """
        The raw contents of the file.  This is usually unsafe because
        it can cause the memory limit to be reached if the file is too
        big.  However this limitation currently affects the whole django
        system which handles uploads in the memory.
        """
        f = self.open()
        try:
            return f.read()
        finally:
            f.close()

    @property
    def html_representation(self):
        """
        This method returns a `HTML` representation of the attachment for the
        `show_action` page.  If this method does not know about an internal
        representation for the object the return value will be an download
        link to the raw attachment.
        """
        url = escape(self.get_absolute_url())
        if self.mimetype.startswith('image/'):
            return u'<a href="%s"><img class="attachment" src="%s" ' \
                   u'alt="%s"></a>' % ((url,) * 3)
        elif self.mimetype.startswith('text/'):
            return highlight_code(self.contents, filename=self.filename)
        else:
            return u'<a href="%s">Anhang herunterladen</a>' % url

    def open(self, mode='rb'):
        """
        Open the file as file descriptor.  Don't forget to close this file
        descriptor accordingly.
        """
        return file(self.get_file_filename(), mode)

    def get_absolute_url(self):
        return self.get_file_url()


class Revision(models.Model):
    """
    Represents a single page revision.  A revision object is always bound to
    a page which is available with the `page` attribute.

    Most of the time `Revision` objects appear as a part of a `Page` object
    for some `actions` however they enter a template context without a page
    object too.

    :IVariables:

        page
            The page this object is operating on.  In the templates however
            you will never have to access this attribute because all revisions
            sent to the template are either part of a bound `Page` or provide
            an extra object for the page itself.

        text
            a `Text` object.  In templates you usually don't have to cope with
            this attribute because it just contains the raw data and not the
            rendered one.  For the rendered data have a look at
            `rendered_text`.

        user
            The user that created this revision.  If an anoymous user created
            the revision this will be `None`.

        change_date
            The date of the revision as `datetime.datetime` object.

        note
            The change note as string.

        deleted
            If the revision is marked as deleted this is `True`.

        remote_addr
            The remote address for the user.  In templates this is a useful
            attribute if you need a replacement for the `user` when no user is
            present.

        attachment
            If the page itself holds an attachment this will point to an
            `Attachment` object.  Otherwise this attribute is `None` and must
            be ignored.
    """
    page = models.ForeignKey(Page, related_name='revisions')
    text = models.ForeignKey(Text, related_name='revisions')
    user = models.ForeignKey(User, related_name='wiki_revisions', null=True,
                             blank=True)
    change_date = models.DateTimeField()
    note = models.CharField(max_length=512)
    deleted = models.BooleanField()
    remote_addr = models.CharField(max_length=200)
    attachment = models.ForeignKey(Attachment, null=True, blank=True)

    @property
    def title(self):
        """
        The page title plus the revision date.  This is equivalent to
        `Page.full_title`.
        """
        return u'%s (Revision %s)' % (
            self.page.title,
            format_specific_datetime(self.change_date)
        )

    @property
    def rendered_text(self):
        """
        The rendered version of the `text` attribute.  This is equivalent
        to calling ``text.render(page=page)``.
        """
        return self.text.render(page=self.page.name)

    def get_absolute_url(self):
        return href('wiki', self.page.name, rev=self.id)

    def revert(self, note=None, user=None, remote_addr=None):
        """Revert this revision and make it the current one."""
        note = (note and note + ' ' or '') + ('[%s wiederhergestellt]' %
                                              self.title)
        new_rev = Revision(page=self.page, text=self.text, user=user or
                           self.user, change_date=datetime.utcnow(),
                           note=note, deleted=False, remote_addr=
                           remote_addr or '127.0.0.1',
                           attachment=self.attachment)
        new_rev.save()
        return new_rev

    def save(self):
        """Save the revision and invalidate the cache."""
        models.Model.save(self)
        cache.delete('wiki/page/' + self.page.name)

    def __unicode__(self):
        return 'Revision %d (%s)' % (
            self.id,
            self.page.name
        )

    def __repr__(self):
        return '<%s %r rev %r>' % (
            self.__class__.__name__,
            self.page.name,
            self.id
        )

    class Meta:
        get_latest_by = 'change_date'
        ordering = ['-change_date']


class MetaData(models.Model):
    """
    Every page (just pages not revisions) can have an unlimited number
    of metadata associated with.  Metadata is useful to add invisible
    information to pages such as tags, acls etc.

    This should be considered being a private class because it is wrapped
    by the `Page.metadata` property and the `Page.update_meta` method.
    """
    page = models.ForeignKey(Page)
    key = models.CharField(max_length=30)
    value = models.CharField(max_length=512)

from inyoka.wiki.parser import nodes
