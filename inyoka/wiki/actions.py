# -*- coding: utf-8 -*-
"""
    inyoka.wiki.actions
    ~~~~~~~~~~~~~~~~~~~

    This module contains all the actions for the wiki.  Actions are bound
    to a page and change the default display for a page.  Per default the
    action is 'show' and displays the most recent revision or the revision
    provided in the URL.  Other actions are 'edit', 'delete', 'info',
    'diff' etc.

    All actions are passed normalized page names because the view function
    that dispatches action ensures that.  If however actions are called from
    a source that deals with user submitted data all page names *must* be
    normalized.  The database models do not do this on their own!


    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from datetime import datetime
from django.db import models
from inyoka.utils.urls import href, url_for
from inyoka.utils.http import templated, does_not_exist_is_404, \
     TemplateResponse, AccessDeniedResponse, PageNotFound, \
     HttpResponseRedirect, HttpResponse
from inyoka.utils.feeds import AtomFeed
from inyoka.utils.flashing import flash
from inyoka.utils.diff3 import merge
from inyoka.utils.templating import render_template
from inyoka.utils.notification import notify_about_subscription
from inyoka.utils.pagination import Pagination
from inyoka.utils.cache import cache
from inyoka.utils.text import normalize_pagename, get_pagetitle, join_pagename
from inyoka.utils.html import escape
from inyoka.utils.urls import url_encode
from inyoka.utils.storage import storage
from inyoka.wiki.models import Page, Revision
from inyoka.wiki.forms import PageEditForm, AddAttachmentForm, \
    EditAttachmentForm, ManageDiscussionForm
from inyoka.wiki.parser import parse, RenderContext
from inyoka.wiki.acl import require_privilege, has_privilege, PrivilegeTest
from inyoka.portal.models import Subscription
from inyoka.portal.utils import simple_check_login
from inyoka.forum.models import Topic


def context_modifier(request, context):
    """
    If a key called ``'page'`` that points to a page object is part of the
    context this modifier will hook a `PrivilegeTest` for the current user
    and that page into the request (called ``can``).  Then the templates
    can test for privileges this way::

        {% if can.read %}...{% endif %}
    """
    if 'page' in context:
        page_name = getattr(context['page'], 'name', None)
        if page_name:
            context['is_subscribed'] = request.user.is_authenticated and \
                Subscription.objects.user_subscribed(request.user,
                                                     wiki_page=context['page'])
            context['can'] = PrivilegeTest(request.user, page_name)


@require_privilege('read')
@templated('wiki/action_show.html', modifier=context_modifier)
def do_show(request, name):
    """
    Show a given revision or the most recent one.  This action requires the
    read privilege.  If a page does not exist yet and no revision was provided
    in the URL it will call `do_missing_page` and return that output.

    Otherwise the page from the database is loaded and displayer.  Because it
    does not catch not found exceptions the `views.show_page` function that
    dispatches the actions automatically renders a missing resource.

    **Template**
        ``'wiki/action_show.html'``

    **Context**
        ``page``
            the bound `Page` object that should be shown.  Because it's bound
            the `rev` attribute points to the requested revision.  Note that
            deleted pages must not be handled in the template because the view
            automatically dispatches to `do_missing_page` if a revision is
            maked as deleted.
    """
    rev = request.GET.get('rev')
    try:
        if rev is None or not rev.isdigit():
            page = Page.objects.get_by_name(name)
            rev = None
        else:
            page = Page.objects.get_by_name_and_rev(name, rev)
    except Page.DoesNotExist:
        return do_missing_page(request, name)
    if request.GET.get('redirect') != 'no':
        redirect = page.metadata.get('X-Redirect')
        if redirect:
            flash(u'Von „<a href="%s">%s</a>“ weitergeleitet.' % (
                escape(href('wiki', page.name, redirect='no')),
                escape(page.title)
            ))
            anchor = None
            if '#' in redirect:
                redirect, anchor = redirect.rsplit('#', 1)
            return HttpResponseRedirect(href('wiki', redirect, redirect='no', _anchor=anchor))
    if page.rev.deleted:
        return do_missing_page(request, name, page)

    if request.user.is_authenticated:
        try:
            s = Subscription.objects.get(wiki_page=page, user=request.user, notified=True)
        except Subscription.DoesNotExist:
            pass
        else:
            s.notified = False
            s.save()

    return {
        'page':         page,
        'tags':         page.metadata['tag'],
        'deny_robots':  rev is not None,
    }


@require_privilege('read')
def do_metaexport(request, name):
    """
    Export metadata as raw text.  This exists mainly for debugging reasons but
    it could make sense for external scripts too that want to get a quick list
    of backlinks etc.  Like the `do_show` action this requires read access to
    the page.
    """
    try:
        page = Page.objects.get_by_name(name)
    except Page.DoesNotExist:
        return HttpResponse(u'', content_type='text/plain; charset=utf-8',
                            status=404)
    metadata = []
    for key, values in page.metadata.iteritems():
        for value in values:
            metadata.append(u'%s: %s' % (key, value))
    return HttpResponse(u'\n'.join(metadata).encode('utf-8'),
                        content_type='text/plain; charset=utf-8')


@templated('wiki/missing_page.html', status=404, modifier=context_modifier)
def do_missing_page(request, name, _page=None):
    """
    Called if a page does not exist yet but it was requested by show.

    **Template**
        ``'wiki/missing_page.html'``

    **Context**
        ``page_name``
            The name of the page that does not exist.

        ``title``
            The title of that page.

        ``similar``
            List of pages with a similar name.  The list contains some dicts
            with ``name`` and ``title`` items.

        ``backlinks``
            Like ``similar`` but contains a list of pages that refer to this
            page with links.
    """
    can_create = has_privilege(request.user, name, 'create')
    if can_create:
        create_link = href('wiki', name, action='edit')
    else:
        new_name = u'%s/%s' % (storage['wiki_newpage_root'], name)
        if has_privilege(request.user, new_name, 'create'):
            create_link = href('wiki', new_name, action='edit')
        else:
            create_link = None

    try:
        not_finished = Page.objects.get_by_name(join_pagename(
            storage['wiki_newpage_root'], name
        ))
    except Page.DoesNotExist:
        not_finished = None

    return {
        'page':         _page,
        'page_name':    name,
        'create_link':  create_link,
        'title':        get_pagetitle(name),
        'similar': [{
            'name':     x,
            'title':    get_pagetitle(x)
        } for x in sorted(Page.objects.get_similar(name))],
        'backlinks': [{
            'name':     x.name,
            'title':    x.title
        } for x in sorted(Page.objects.find_by_metadata('X-Link', name),
                          key=lambda x: x.title.lower())],
        'not_finished': not_finished
    }


@require_privilege('manage')
@does_not_exist_is_404
def do_revert(request, name):
    """The revert action has no template, it uses a flashed form."""
    try:
        rev = int(request.GET['rev'])
    except (KeyError, ValueError):
        raise PageNotFound()
    url = href('wiki', name, rev=rev)
    page = Page.objects.get_by_name_and_rev(name, rev)
    latest_rev = page.revisions.latest()
    if latest_rev == page.rev:
        flash(u'Keine Änderungen durchgeführt, da die Revision '
              u'bereits die aktuelle ist.', success=False)
    elif request.method == 'POST':
        if 'cancel' in request.POST:
            flash(u'Wiederherstellen abgebrochen.')
            url = href('wiki', name, rev=page.rev.id)
        else:
            new_revision = page.rev.revert(request.POST.get('note'),
                                           request.user,
                                           request.META.get('REMOTE_ADDR'))
            page.last_rev = new_revision
            flash(u'Die %s wurde erfolgreich wiederhergestellt.' %
                  escape(page.rev.title), success=True)
            url = href('wiki', name)
    else:
        flash(render_template('wiki/action_revert.html', {'page': page}))
    return HttpResponseRedirect(url)


@require_privilege('manage')
@does_not_exist_is_404
def do_rename(request, name):
    """Rename all revisions."""
    page = Page.objects.get_by_name(name, raise_on_deleted=True)
    new_name = request.GET.get('page_name') or page.name
    force = request.GET.get('force', False)
    if request.method == 'POST':
        force = request.POST.get('force', False)
        new_name = normalize_pagename(request.POST.get('new_name', ''))
        if not new_name:
            flash(u'Kein Seitenname eingegeben.', success=False)
        else:
            try:
                Page.objects.get_by_name(new_name)
            except Page.DoesNotExist:
                # check that there are no dublicate attachments existing
                # pointing to the new page name.
                new_page_attachments = (p.split('/')[-1] for p in
                                        Page.objects.get_attachment_list(new_name, False))
                old_page_attachments = (p.split('/')[-1] for p in
                                        Page.objects.get_attachment_list(page.name, False))
                dublicate = set(new_page_attachments).intersection(set(old_page_attachments))
                if dublicate and not force:
                    linklist = u', '.join('<a href="%s">%s</a>' %
                        (join_pagename(new_name, name), name.split('/')[-1])
                        for name in dublicate)
                    flash(u'Folgende Anhänge sind bereits dem neuen Seitennamen zugeordnet: %s.'
                          u' Bitte stelle sicher das diese nicht mehr benötigt werden. '
                          u' <a href="%s">Umbenennen und Löschung doppelter Anhänge erzwingen</a>'
                          % (linklist, href('wiki', page.name, action='rename', force=True)), False)
                    return HttpResponseRedirect(url_for(page))
                elif dublicate and force:
                    for attachment in dublicate:
                        obj = Page.objects.get_by_name(join_pagename(new_name, attachment))
                        models.Model.delete(obj)

                page.name = new_name
                page.edit(note=u'Umbenannt von %s' % name, user=request.user,
                          remote_addr=request.META.get('REMOTE_ADDR'))

                if request.POST.get('add_redirect'):
                    #TODO: if a page was renamed sometime before
                    #      the old redirect points to the wrong
                    #      place. I have no idea how to handle that --entequak
                    old_text = u'# X-Redirect: %s\n' % new_name
                    Page.objects.create(
                        name=name, text=old_text, user=request.user,
                        note=u'Umbenannt nach %s' % page.name,
                        remote_addr=request.META.get('REMOTE_ADDR'))

                # move all attachments
                for attachment in Page.objects.get_attachment_list(name):
                    ap = Page.objects.get_by_name(attachment)
                    old_attachment_name = ap.name
                    ap.name = normalize_pagename(join_pagename(page.trace[-1],
                                                              ap.short_title))
                    ap.edit(note=u'Umbenannt von %s' % old_attachment_name,
                            remote_addr=request.META.get('REMOTE_ADDR'))

                cache.delete('wiki/page/' + name)
                cache.delete('wiki/object_list')
                flash(u'Die Seite wurde erfolgreich umbenannt.', success=True)
                return HttpResponseRedirect(url_for(page))
            else:
                flash(u'Eine Seite mit diesem Namen existiert bereits.', False)
                return HttpResponseRedirect(href('wiki', name))
        return HttpResponseRedirect(url_for(page))
    flash(render_template('wiki/action_rename.html', {
        'page':         page,
        'new_name':     new_name,
        'force':        force
    }))
    return HttpResponseRedirect(url_for(page, 'show_no_redirect'))


@require_privilege('edit')
@templated('wiki/action_edit.html', modifier=context_modifier)
def do_edit(request, name):
    """
    Edit or create a wiki page.  If the page is an attachment this displays a
    form to update the attachment next to the description box.  If it's a
    normal page or no page yet this just displays a text box for the page
    text and an input field for the change note.
    If the user is not logged in, he gets a warning that his IP will be
    visible for everyone until Sankt-nimmerleinstag (forever).

    **Template**
        ``'wiki/action_edit.html'``

    **Context**
        ``name``
            The name of the page that is edited.

        ``page``
            The `Page` object of the page that is edited.  This only exists
            if a page is edited, not if a page is created.

        ``form``
            A `PageEditForm` instance.

        ``preview``
            If we are in preview mode this is a rendered HTML preview.
    """
    rev = request.REQUEST.get('rev')
    rev = rev is not None and rev.isdigit() and int(rev) or None
    try:
        page = Page.objects.get_by_name_and_rev(name, rev)
    except Page.DoesNotExist:
        page = None
        if not has_privilege(request.user, name, 'create'):
            if has_privilege(request.user, u'%s/%s' % (
                                           storage['wiki_newpage_template'],
                                           name),
                             'create'):
                return HttpResponseRedirect(href('wiki', storage['wiki_newpage_template'], name, action='edit'))
            return AccessDeniedResponse()
        current_rev_id = ''
    else:
        # If the page is deleted it requires creation privilege
        if page.rev.deleted and not has_privilege(request.user, name, 'create'):
            return AccessDeniedResponse()
        current_rev_id = str(page.rev.id)

    # attachments have a custom editor
    if page and page.rev.attachment:
        return do_attach_edit(request, page.name)

    # form defaults
    form_data = request.POST.copy()
    preview = None
    form = PageEditForm()
    if page is not None:
        form.initial = {'text': page.rev.text.value}
    else:
        form.initial = {'text': storage['wiki_newpage_template'] or ''}

    # if there a template is in use, load initial text from the template
    template = request.GET.get('template')
    if not request.method == 'POST' and template and \
       has_privilege(request.user, template, 'read'):
        try:
            template = Page.objects.get_by_name(template)
        except Page.DoesNotExist:
            pass
        else:
            form.initial['text'] = template.rev.text.value
            flash(u'Die Vorlage “<a href="%s">%s</a>” wurde geladen und '
                  u'wird als Basis für die neue Seite verwendet.' %
                  (url_for(template), escape(template.name)))

    # check for edits by other users.  If we have such an edit we try
    # to merge and set the edit time to the time of the last merge or
    # conflict.  We do that before the actual form processing
    merged_this_request = False
    try:
        # Don't change to utcfromtimestamp, the data is already in utc.
        edit_time = datetime.fromtimestamp(int(request.POST['edit_time']))
    except (KeyError, ValueError):
        edit_time = datetime.utcnow()
    if rev is None:
        latest_rev = page and page.rev or None
    else:
        try:
            latest_rev = Page.objects.get_by_name(name).rev
        except Page.DoesNotExist:
            latest_rev = None
    if latest_rev is not None and edit_time < latest_rev.change_date:
        form_data['text'] = merge(page.rev.text.value,
                                  latest_rev.text.value,
                                  form_data.get('text', ''))
        edit_time = latest_rev.change_date
        merged_this_request = True

    # form validation and handling
    if request.method == 'POST':
        if request.POST.get('cancel'):
            flash(u'Bearbeitungsvorgang wurde abgebrochen.')
            if page and page.metadata.get('redirect'):
                url = href('wiki', page.name, redirect='no')
            else:
                url = href('wiki', name)
            return HttpResponseRedirect(url)
        elif request.POST.get('preview'):
            text = request.POST.get('text') or ''
            context = RenderContext(request, page)
            preview = parse(text).render(context, 'html')
            form.initial['text'] = text
        else:
            form = PageEditForm(request.user, name, page and
                                page.rev.text.value or '', form_data)
            if form.is_valid() and not merged_this_request:
                remote_addr = request.META.get('REMOTE_ADDR')
                if page is not None:
                    if form.cleaned_data['text'] == page.rev.text.value:
                        flash(u'Keine Änderungen.')
                    else:
                        action = page.rev.deleted and u'angelegt' or u'bearbeitet'
                        page.edit(user=request.user,
                                  deleted=False,
                                  remote_addr=remote_addr,
                                  **form.cleaned_data)
                        flash(u'Die Seite „<a href="%s">%s</a>“ wurde '
                              u'erfolgreich %s.' % (
                            escape(href('wiki', page.name)),
                            escape(page.name),
                            action
                        ), True)
                else:
                    page = Page.objects.create(user=request.user,
                                               remote_addr=remote_addr,
                                               name=name,
                                               **form.cleaned_data)
                    flash(u'Die Seite „<a href="%s">%s</a>“ wurde '
                          u'erfolgreich angelegt.' % (
                        escape(href('wiki', page.name)),
                        escape(page.name)
                    ), True)

                # send notifications
                for s in Subscription.objects.filter(wiki_page=page,
                                                     notified=False) \
                                             .exclude(user=request.user):
                    rev, old_rev = page.revisions.all()[:2]
                    notify_about_subscription(s, 'page_edited',
                        u'Die Seite „%s“ wurde geändert' % page.title, {
                              'username': s.user.username,
                              'rev':      rev,
                              'old_rev':  old_rev,
                    })
                    s.notified = True
                    s.save()

                if page.metadata.get('redirect'):
                    url = href('wiki', page.name, redirect='no')
                else:
                    url = href('wiki', page.name)
                return HttpResponseRedirect(url)
    elif not request.user.is_authenticated:
        flash(u'Du bearbeitest diese Seite unangemeldet. Wenn du speicherst, '
              u'wird deine aktuelle IP-Adresse in der Versionsgeschichte '
              u'aufgezeichnet und ist damit unwiderruflich öffentlich '
              u'einsehbar.')


    # if we have merged this request we should inform the user about that,
    # and that we haven't saved the page yet.
    if merged_this_request:
        flash(u'Während du die Seite geöffnet hattest wurde sie von '
              u'einem anderen Benutzer ebenfalls bearbeitet.  Bitte '
              u'kontrolliere, ob das Zusammenführen der Änderungen '
              u'zufriedenstellend funktioniert hat.')

    return {
        'name':         name,
        'page':         page,
        'form':         form,
        'preview':      preview,
        'edit_time':    edit_time.strftime('%s'),
        'rev':          current_rev_id,
        'storage':      storage,
        'deny_robots':  True,
    }


@require_privilege('delete')
@does_not_exist_is_404
def do_delete(request, name):
    """Delete the page (deletes the last recent revision)."""
    page = Page.objects.get_by_name(name, raise_on_deleted=True)
    if request.method == 'POST':
        if 'cancel' in request.POST:
            flash(u'Bearbeiten wurde abgebrochen')
        else:
            page.edit(user=request.user, deleted=True,
                      remote_addr=request.META.get('REMOTE_ADDR'),
                      note=request.POST.get('note', '') or
                           u'Seite wurde gelöscht')
            flash(u'Seite wurde erfolgreich gelöscht', success=True)
    else:
        flash(render_template('wiki/action_delete.html', {'page': page}))
    return HttpResponseRedirect(url_for(page))


@require_privilege('read')
@templated('wiki/action_log.html', modifier=context_modifier)
def do_log(request, name):
    """
    Show a revision log for this page.

    **Template**
        ``'wiki/action_log.html'``

    **Context**
        ``page``
            The `Page` object this template action renders the revision
            log of.  It's unbound thus the `rev` attribute is `None`.

        ``revisions``
            The list of revisions ordered by date.  The newest revision
            first.
    """
    try:
        pagination_page = int(request.GET['page'])
    except (ValueError, KeyError):
        pagination_page = 1
    page = Page.objects.get(name__iexact=name)

    def link_func(p, parameters):
        if p == 1:
            parameters.pop('page', None)
        else:
            parameters['page'] = str(p)
        rv = url_for(page)
        if parameters:
            rv += '?' + url_encode(parameters)
        return rv

    if request.GET.get('format') == 'atom':
        feed = AtomFeed(u'Seitenrevisionen von „%s“' % page.name,
                        url=url_for(page),
                        feed_url=request.build_absolute_uri(),
                        rights=href('portal', 'lizenz'),
                        icon=href('static', 'img', 'favicon.ico'))

        for rev in page.revisions.all()[:15]:
            feed.add(title=rev.title, url=url_for(rev),
                     author=rev.user and rev.user.username or rev.remote_addr,
                     published=rev.change_date, updated=rev.change_date)
        return HttpResponse(feed.to_string(), content_type='application/atom+xml; charset=utf-8')

    pagination = Pagination(request, page.revisions.all(), pagination_page,
                            20, link_func)
    return {
        'page':         page,
        'revisions':    list(pagination.objects),
        'pagination':   pagination,
        'deny_robots':  True,
    }


@require_privilege('read')
@templated('wiki/action_diff.html', modifier=context_modifier)
def do_diff(request, name):
    """Render a diff between two pages."""
    old_rev = request.GET.get('rev', '')
    if not old_rev.isdigit():
        old_rev = Page.objects.get_head(name, -1)
        if old_rev is None:
            raise Revision.DoesNotExist()
    new_rev = request.GET.get('new_rev') or None
    if new_rev and not new_rev.isdigit():
        raise PageNotFound()
    diff = Page.objects.compare(name, old_rev, new_rev)
    if request.GET.get('format') == 'udiff':
        return HttpResponse(diff.udiff, mimetype='text/plain; charset=utf-8')

    return {
        'diff':         diff,
        'page':         diff.page,
        'deny_robots':  True,
    }


@require_privilege('read')
@templated('wiki/action_backlinks.html', modifier=context_modifier)
def do_backlinks(request, name):
    """
    Display a list of backlinks.

    Because this is part of the pathbar that is displayed for deleted pages
    it should not fail for deleted pages!  Additionally it probably makes
    sense to track pages that link to a deleted page.
    """
    page = Page.objects.get_by_name(name)

    return {
        'page': page,
        'deny_robots':  True,
    }


@require_privilege('read')
@does_not_exist_is_404
def do_export(request, name):
    """
    Export the given revision or the most recent one to the specified format
    (raw, html, ast or docbook so far).

    =============== ======= ==================================================
    Format          Partial Full    Description
    =============== ======= ==================================================
    ``raw``         yes     no      The raw wiki markup exported.
    ``HTML``        yes     yes     The wiki markup converted to HTML4.
    ``Docbook``     yes     yes     The wiki markup converted to docbook.
    ``AST``         yes     no      The wiki markup as internal abstract
                                    syntax tree.  Useful for debugging.
    =============== ======= ==================================================


    **Template**
        Depending on the output format either no template at all or one of
        the following ones:
        -   ``'wiki/export_docbook.xml'``
        -   ``'wiki/export.html'``

    **Context**
        The context is of course only passed if a template is rendered but
        the same for all the templates.

        ``fragment``
            `True` if a fragment should be rendered (no xml preamble etc)

        ``page``
            The bound `Page` object which should be rendered.
    """
    rev = request.GET.get('rev')
    if rev is None or not rev.isdigit():
        page = Page.objects.get_by_name(name, raise_on_deleted=True)
    else:
        page = Page.objects.get_by_name_and_rev(name, rev,
                                                raise_on_deleted=True)
    ctx = {
        'fragment': request.GET.get('fragment', 'no') == 'yes',
        'page':     page
    }
    format = request.GET.get('format', 'raw').lower()
    if format == 'docbook':
        return TemplateResponse('wiki/export_docbook.xml', ctx,
                                content_type='application/docbook+xml; '
                                'charset=utf-8')
    elif format == 'html':
        return TemplateResponse('wiki/export.html', ctx,
                                content_type='text/html; charset=utf-8')
    elif format == 'ast':
        return HttpResponse(repr(page.rev.text.parse()),
                            content_type='text/plain; charset=ascii')
    else:
        return HttpResponse(page.rev.text.value.encode('utf-8'),
                            content_type='text/plain; charset=utf-8')


@require_privilege('attach')
@templated('wiki/action_attach.html', modifier=context_modifier)
def do_attach(request, name):
    """
    List all pages with attachments according to the given page and
    allow the user to attach new files.

    **Template**
        ``'wiki/action_attach.html'``

    **Context**
        ``page``
            The `Page` that owns the attachment

        ``attachments``
            A list of `Page` objects that are attachments and below this
            page.  They all have a proper attachment attributes which is
            an `Attachment`.

        ``form``
            An `AddAttachmentForm` instance.
    """
    page = Page.objects.get_by_name(name)
    if page.rev.attachment_id is not None:
        flash(u'Anhänge in Anhängen sind nicht erlaubt!', False)
        return HttpResponseRedirect(url_for(page))
    attachments = Page.objects.get_attachment_list(name)
    attachments = [Page.objects.get_by_name(i) for i in attachments]
    context = {
        'page':        Page.objects.get_by_name(name),
        'attachments': attachments,
        'form':        AddAttachmentForm()
    }
    if request.method == 'POST':
        if request.POST.get('cancel'):
            flash(u'Hinzufügen des Dateianhangs abgebrochen.')
            if page and page.metadata.get('redirect'):
                url = href('wiki', page.name, redirect='no')
            else:
                url = href('wiki', name)
            return HttpResponseRedirect(url)
        form = AddAttachmentForm(request.POST, request.FILES)
        if not form.is_valid():
            context['form'] = form
            return context
        d = form.cleaned_data
        attachment_name = d.get('filename') or d['attachment'].name
        filename = d['attachment'].name or d.get('filename')
        if not attachment_name:
            flash(u'Bitte gib einen Dateinamen für den Anhang an.')
            return context
        attachment_name = u'%s/%s' % (name, attachment_name)
        attachment_name = normalize_pagename(attachment_name.strip('/'))
        try:
            ap = Page.objects.get_by_name(attachment_name)
        except Page.DoesNotExist:
            ap = None
        if ap is not None and (ap.rev.attachment is None or
                               not d.get('override', False)):
            flash(u'Es existiert bereits eine Seite oder ein Anhang mit ' +
                  'diesem Namen.', False)
            return context
        remote_addr = request.META.get('REMOTE_ADDR')
        if ap is None:
            ap = Page.objects.create(user=request.user,
                                     text=d.get('text', u''),
                                     remote_addr=remote_addr,
                                     name=attachment_name,
                                     note=d.get('note', u''),
                                     attachment_filename=filename,
                                     attachment=d['attachment'])
        else:
            ap.edit(user=request.user,
                    text=d.get('text', ap.rev.text),
                    remote_addr=remote_addr,
                    note=d.get('note', u''),
                    attachment_filename=filename,
                    attachment=d['attachment'])
        flash(u'Der Dateianhang wurde erfolgreich gespeichert.', True)
        if ap.metadata.get('weiterleitung'):
            url = href('wiki', ap, redirect='no')
        else:
            url = href('wiki', ap)
        return HttpResponseRedirect(url)

    context['deny_robots'] = 'noindex'
    return context


@require_privilege('attach')
@templated('wiki/action_attach_edit.html', modifier=context_modifier)
def do_attach_edit(request, name):
    page = Page.objects.get_by_name(name)
    form = EditAttachmentForm({
        'text': page.rev.text.value,
    })
    if request.method == 'POST':
        form = EditAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            d = form.cleaned_data
            attachment = None
            attachment_filename = None
            if d['attachment']:
                attachment = d['attachment']
                attachment_filename = d['attachment'].name or \
                                        page.rev.attachment.filename
            page.edit(user=request.user,
                        text=d.get('text', page.rev.text.value),
                        remote_addr=request.META.get('remote_addr'),
                        note=d.get('note', u''),
                        attachment_filename=attachment_filename,
                        attachment=attachment)
            flash(u'Der Dateianhang wurde erfolgreich bearbeitet.', True)
            return HttpResponseRedirect(url_for(page))
    return {
        'form': form,
        'page': page
    }


@does_not_exist_is_404
def do_prune(request, name):
    """Clear the page cache."""
    page = Page.objects.get_by_name(name)
    page.prune()
    flash(u'Der Seitencache wurde geleert.', True)
    return HttpResponseRedirect(url_for(page))


@templated('wiki/action_manage.html', modifier=context_modifier)
def do_manage(request, name):
    """
    Show a list of all actions for this page.

    **Template**
        ``'wiki/action_manage.html'``
    """
    return {
        'page':         Page.objects.get_by_name(name),
        'deny_robots':  True,
    }


@simple_check_login
def do_subscribe(request, page_name):
    """
    Subscribe the user to the page with `page_name`
    """
    p = Page.objects.get(name__iexact=page_name)
    if not Subscription.objects.filter(user=request.user, wiki_page=p).exists():
        # there's no such subscription yet, create a new one
        Subscription(user=request.user, wiki_page=p).save()
        flash(u'Du wirst ab jetzt bei Veränderungen dieser Seite '
              u'benachrichtigt.', True)
    else:
        flash(u'Du wirst bereits benachrichtigt')
    return HttpResponseRedirect(url_for(p))


@simple_check_login
def do_unsubscribe(request, page_name):
    """
    Unsubscribe the user from the page with `page_name`
    """
    p = Page.objects.get(name__iexact=page_name)
    try:
        s = Subscription.objects.get(user=request.user, wiki_page=p)
    except Subscription.DoesNotExist:
        flash(u'Du wirst über diese Seite gar nicht benachrichtigt!')
    else:
        s.delete()
        flash(u'Du wirst ab jetzt bei Veränderungen dieser Seite '
              u'nicht mehr benachrichtigt.', True)
    return HttpResponseRedirect(url_for(p))

@require_privilege('edit')
@does_not_exist_is_404
@templated('wiki/action_manage_discussion.html')
def do_manage_discussion(request, name):
    page = Page.objects.get(name=name)
    if request.method == 'POST':
        form = ManageDiscussionForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if data['topic']:
                page.topic_id = data['topic'].id
                page.save()
                return HttpResponseRedirect(url_for(data['topic']))
            else:
                page.topic_id = None
                page.save()
                return HttpResponseRedirect(url_for(page))
    elif page.topic_id is None:
        form = ManageDiscussionForm()
    else:
        topic = Topic.query.get(page.topic_id)
        form = ManageDiscussionForm(initial={'topic': topic.slug})
    return {
        'page': page,
        'form': form,
    }

PAGE_ACTIONS = {
    'show':              do_show,
    'metaexport':        do_metaexport,
    'log':               do_log,
    'diff':              do_diff,
    'revert':            do_revert,
    'rename':            do_rename,
    'edit':              do_edit,
    'delete':            do_delete,
    'backlinks':         do_backlinks,
    'export':            do_export,
    'attach':            do_attach,
    'prune':             do_prune,
    'manage':            do_manage,
    'subscribe':         do_subscribe,
    'unsubscribe':       do_unsubscribe,
    'manage_discussion': do_manage_discussion,
}
