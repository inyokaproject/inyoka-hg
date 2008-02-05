# -*- coding: utf-8 -*-
"""
    inyoka.wiki.actions
    ~~~~~~~~~~~~~~~~~~~

    This module contains all the actions for the wiki. Actions are bound
    to a page and change the default display for a page. Per default the
    action is 'show' and displays the most recent revision or the revision
    provided in the URL. Other actions are 'edit', 'delete', 'info',
    'diff' etc.

    All actions are passed normalized page names because the view function
    that dispatches action ensures that. If however actions are called from
    a source that deals with user submitted data all page names *must* be
    normalized. The database models do not do this on their own!


    :copyright: Copyright 2007 by Armin Ronacher, Christoph Hack,
                                  Benjamin Wiegand.
    :license: GNU GPL.
"""
from time import localtime
from datetime import datetime
from django.utils.html import escape
from django.http import HttpResponseRedirect, Http404 as PageNotFound, \
     HttpResponse
from inyoka.utils.urls import href, url_for
from inyoka.utils.http import templated, does_not_exist_is_404, \
     TemplateResponse, AccessDeniedResponse
from inyoka.utils.flashing import flash
from inyoka.utils.diff3 import merge
from inyoka.utils.sessions import set_session_info
from inyoka.utils.templating import render_template
from inyoka.utils.notification import send_notification
from inyoka.utils.pagination import Pagination
from inyoka.utils.feeds import FeedBuilder
from inyoka.wiki.models import Page, Revision
from inyoka.wiki.forms import PageEditForm, AddAttachmentForm, EditAttachmentForm
from inyoka.wiki.parser import parse, RenderContext
from inyoka.wiki.utils import get_title, normalize_pagename
from inyoka.wiki.acl import require_privilege, has_privilege, \
     test_changes_allowed, PrivilegeTest
from inyoka.portal.models import Subscription
from inyoka.portal.utils import simple_check_login


def context_modifier(request, context):
    """
    If a key called ``'page'`` that points to a page object is part of the
    context this modifier will hook a `PrivilegeTest` for the current user
    and that page into the request (called ``can``). Then the templates
    can test for privileges this way::

        {% if can.read %}...{% endif %}
    """
    if 'page' in context:
        page_name = getattr(context['page'], 'name', None)
        context['is_subscribed'] = bool(Subscription.objects.filter(
            wiki_page__name=page_name))
        if page_name:
            context['can'] = PrivilegeTest(request.user, page_name)


@require_privilege('read')
@templated('wiki/action_show.html', modifier=context_modifier)
def do_show(request, name):
    """
    Show a given revision or the most recent one. This action requires the
    read privilege. If a page does not exist yet and no revision was provided
    in the URL it will call `do_missing_page` and return that output.

    Otherwise the page from the database is loaded and displayer. Because it
    does not catch not found exceptions the `views.show_page` function that
    dispatches the actions automatically renders a missing resource.

    **Template**
        ``'wiki/action_show.html'``

    **Context**
        ``page``
            the bound `Page` object that should be shown. Because it's bound
            the `rev` attribute points to the requested revision. Note that
            deleted pages must not be handled in the template because the view
            automatically dispatches to `do_missing_page` if a revision is
            maked as deleted.
    """
    rev = request.GET.get('rev')
    try:
        if rev is None or not rev.isdigit():
            page = Page.objects.get_by_name(name)
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
            return HttpResponseRedirect(href('wiki', redirect))
    if page.rev.deleted:
        return do_missing_page(request, name, page)

    set_session_info(request, u'betrachtet Wiki Artikel „<a '
                     u'href="%s">%s</a>“' % (
                        escape(url_for(page)),
                        escape(page.title)))
    return {
        'page':     page
    }


@require_privilege('read')
def do_metaexport(request, name):
    """
    Export metadata as raw text. This exists mainly for debugging reasons but
    it could make sense for external scripts too that want to get a quick list
    of backlinks etc. Like the `do_show` action this requires read access to
    the page.
    """
    page = Page.objects.get_by_name(name)
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
            List of pages with a similar name. The list contains some dicts
            with ``name`` and ``title`` items.

        ``backlinks``
            Like ``similar`` but contains a list of pages that refer to this
            page with links.
    """
    return {
        'page':         _page,
        'page_name':    name,
        'title':        get_title(name),
        'can_create':   has_privilege(request.user, name, 'create'),
        'similar': [{
            'name':     x,
            'title':    get_title(x)
        } for x in sorted(Page.objects.get_similar(name))],
        'backlinks': [{
            'name':     x.name,
            'title':    x.title
        } for x in sorted(Page.objects.find_by_metadata('X-Link', name),
                          key=lambda x: x.title.lower())]
    }


@require_privilege('edit')
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
            flash('Wiederherstellen abgebrochen.')
            url = href('wiki', name, rev=page.rev.id)
        else:
            new_revision = page.rev.revert(request.POST.get('note'),
                                           request.user,
                                           request.META.get('REMOTE_ADDR'))
            flash(u'Die %s wurde erfolgreich wiederhergestellt.' %
                  unicode(page.rev).title, success=True)
            url = href('wiki', name)
    else:
        flash(render_template('wiki/action_revert.html', {'page': page}))
    return HttpResponseRedirect(url)


@require_privilege('edit')
@does_not_exist_is_404
def do_move(request, name):
    """Move the most recent revision."""
    page = Page.objects.get_by_name(name, raise_on_deleted=True)
    new_name = request.GET.get('page_name') or page.name
    if request.method == 'POST':
        new_name = normalize_pagename(request.POST.get('new_name', ''))
        if 'cancel' in request.POST:
            flash('Verschieben abgebrochen.')
        elif not new_name:
            flash('Kein Seitenname eingegeben.', success=False)
        else:
            try:
                Page.objects.get_by_name(new_name)
            except Page.DoesNotExist:
                original_text = page.rev.text
                page.edit('# X-Redirect: %s\n' % new_name,
                          note='Umbenannt nach %s' % new_name,
                          remote_addr=request.META.get('REMOTE_ADDR'),
                          user=request.user)
                new_page = Page.objects.create(new_name, original_text,
                           request.user, note='Umbenannt von %s' % page.name,
                           remote_addr=request.META.get('REMOTE_ADDR'))
                flash('Die Seite wurde erfolgreich umbenannt.', success=True)
                return HttpResponseRedirect(url_for(new_page))
            else:
                flash('Eine Seite mit diesem Namen existiert bereits.')
                rename_url=href('wiki', name, action='move',
                                page_name=new_name)
                return HttpResponseRedirect(rename_url)
        return HttpResponseRedirect(url_for(page))
    flash(render_template('wiki/action_move.html', {
        'page':         page,
        'new_name':     new_name
    }))
    return HttpResponseRedirect(url_for(page))


@require_privilege('edit')
@does_not_exist_is_404
def do_rename(request, name):
    """Rename all revisions."""
    page = Page.objects.get_by_name(name, raise_on_deleted=True)
    new_name = request.GET.get('page_name') or page.name
    if request.method == 'POST':
        new_name = normalize_pagename(request.POST.get('new_name', ''))
        if 'cancel' in request.POST:
            flash('Umbenennen abgebrochen.')
        elif not new_name:
            flash('Kein Seitenname eingegeben.', success=False)
        else:
            try:
                Page.objects.get_by_name(new_name)
            except Page.DoesNotExist:
                page.name = new_name
                page.edit(note='Umbenannt von %s' % name, user=request.user,
                          remote_addr=request.META.get('REMOTE_ADDR'))
                old_text = '# X-Redirect: %s\n' % new_name
                new_page = Page.objects.create(name, old_text, request.user,
                           note='Umbenannt nach %s' % page.name,
                           remote_addr=request.META.get('REMOTE_ADDR'))
                flash('Die Seite wurde erfolgreich umbenannt.', success=True)
                return HttpResponseRedirect(url_for(page))
            else:
                flash('Eine Seite mit diesem Namen existiert bereits.')
                rename_url=href('wiki', name, action='rename',
                                page_name=new_name)
                return HttpResponseRedirect(rename_url)
        return HttpResponseRedirect(url_for(page))
    flash(render_template('wiki/action_rename.html', {
        'page':         page,
        'new_name':     new_name
    }))
    return HttpResponseRedirect(url_for(page))


@require_privilege('edit')
@templated('wiki/action_edit.html', modifier=context_modifier)
def do_edit(request, name):
    """
    Edit or create a wiki page. If the page is an attachment this displays a
    form to update the attachment next to the description box. If it's a
    normal page or no page yet this just displays a text box for the page
    text and an input field for the change note.

    **Template**
        ``'wiki/action_edit.html'``

    **Context**
        ``name``
            The name of the page that is edited.

        ``page``
            The `Page` object of the page that is edited. This only exists
            if a page is edited, not if a page is created.

        ``form``
            A `PageEditForm` instance.

        ``preview``
            If we are in preview mode this is a rendered HTML preview.
    """
    rev = request.GET.get('rev')
    if rev is not None and not rev.isdigit():
        rev = None
    try:
        page = Page.objects.get_by_name_and_rev(name, rev)
    except Page.DoesNotExist:
        page = None
        if not has_privilege(request.user, name, 'create'):
            return AccessDeniedResponse()

    if page and page.rev.attachment:
        return do_attach_edit(request, page.name)

    # form defaults
    form_data = request.POST.copy()
    preview = None
    form = PageEditForm()
    if page is not None:
        form.initial = {'text': page.rev.text.value}

    # check for edits by other users.  If we have such an edit we try
    # to merge and set the edit time to the time of the last merge or
    # conflict.  We do that before the actual form processing
    merged_this_request = False
    try:
        edit_time = datetime(*localtime(int(request.POST['edit_time']))[:7])
    except (KeyError, ValueError):
        edit_time = datetime.now()
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
            flash('Bearbeitungsvorgang wurde abgebrochen.')
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
            form = PageEditForm(form_data)
            if form.is_valid() and not merged_this_request:
                if not test_changes_allowed(request.user, name, page and
                                            page.rev.text.value or '',
                                            form.cleaned_data['text']):
                    raise RuntimeError('security error. XXX: render error')
                remote_addr = request.META.get('REMOTE_ADDR')
                if page is not None:
                    if form.cleaned_data['text'] == page.rev.text.value:
                        flash(u'Keine Änderungen.')
                    else:
                        page.edit(user=request.user,
                                  remote_addr=remote_addr,
                                  **form.cleaned_data)
                        flash(u'Die Seite „<a href="%s">%s</a>“ wurde '
                              u'erfolgreich bearbeitet.' % (
                            escape(href('wiki', page.name)),
                            escape(page.name)
                        ))
                else:
                    page = Page.objects.create(user=request.user,
                                               remote_addr=remote_addr,
                                               name=name,
                                               **form.cleaned_data)
                    flash(u'Die Seite „<a href="%s">%s</a>“ wurde '
                          u'erfolgreich angelegt.' % (
                        escape(href('wiki', page.name)),
                        escape(page.name)
                    ))

                # send notifications
                for s in Subscription.objects.filter(wiki_page=page) \
                                             .exclude(user=request.user):
                    text = render_template('mails/page_edited.txt', {
                        'username': s.user.username,
                        'rev':      page.revisions.latest()
                    })
                    send_notification(s.user, u'Die Seite „%s“ wurde bearbeitet'
                                      % page.title, text)


                if page.metadata.get('weiterleitung'):
                    url = href('wiki', page.name, redirect='no')
                else:
                    url = href('wiki', page.name)
                return HttpResponseRedirect(url)

    # if we have merged this request we should inform the user about that,
    # and that we haven't saved the page yet.
    if merged_this_request:
        flash(u'Während du die Seite geöffnet hattest wurde sie von '
              u'einem anderen Benutzer ebenfalls bearbeitet.  Bitte '
              u'kontrolliere ob das Zusammenführen der Änderungen '
              u'zufriedenstellend funktioniert hat.')

    # update session info
    if page is not None:
        session_page = u'<a href="%s">%s</a>' % (
            escape(url_for(page)),
            escape(page.title)
        )
    else:
        session_page = escape(get_title(name))
    set_session_info(request, u'bearbeitet den Wiki Artikel %s' %
                     session_page)

    return {
        'name':         name,
        'page':         page,
        'form':         form,
        'preview':      preview,
        'edit_time':    int(edit_time.strftime('%s'))
    }


@require_privilege('delete')
@does_not_exist_is_404
def do_delete(request, name):
    """Delete the page (deletes the last recent revision)."""
    page = Page.objects.get_by_name(name, raise_on_deleted=True)
    if request.method == 'POST':
        if 'cancel' in request.POST:
            flash('Bearbeiten wurde abgebrochen')
        else:
            page.edit(user=request.user, deleted=True,
                      remote_addr=request.META.get('REMOTE_ADDR'),
                      note=request.POST.get('note', '') or
                           'Seite wurde gelöscht')
            flash('Seite wurde erfolgreich gelöscht', success=True)
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
            log of. It's unbound thus the `rev` attribute is `None`.

        ``revisions``
            The list of revisions ordered by date. The newest revision
            first.
    """
    try:
        pagination_page = int(request.GET['page'])
    except (ValueError, KeyError):
        pagination_page = 1
    page = Page.objects.get(name=name)

    def link_func(p, parameters):
        if p == 1:
            parameters.pop('page', None)
        else:
            parameters['page'] = str(p)
        rv = url_for(page)
        if parameters:
            rv += '?' + parameters.urlencode()
        return rv

    if request.GET.get('format') == 'atom':
        feed = FeedBuilder(
            title=u'Seitenrevisionen von „%s“' % page.name,
            url=url_for(page),
            feed_url=request.build_absolute_uri(),
            rights=href('portal', 'lizenz')
        )

        for rev in page.revisions.all()[:15]:
            feed.add(title=rev.title, url=url_for(rev),
                     author=rev.user and rev.user.username or rev.remote_addr,
                     published=rev.change_date, updated=rev.change_date)
        return feed.get_atom_response()

    pagination = Pagination(request, page.revisions.all(), pagination_page,
                            20, link_func)
    set_session_info(request, u'betrachtet die Revisionen des Artkels „<a '
                     u'href="%s">%s</a>“' % (
                        escape(url_for(page)),
                        escape(page.title)),
                    "%s' Revisionen" % escape(page.title))

    return {
        'page':         page,
        'revisions':    pagination.get_objects(),
        'pagination':   pagination
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
    set_session_info(request, u'vergleicht zwei Revisionen des Wiki Artikels '
                     u' „<a href="%s">%s</a>“' % (
                        escape(url_for(diff.page)),
                        escape(diff.page.title)))
    return {
        'diff':     diff,
        'page':     diff.page
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
    set_session_info(request, u'vergleicht die Backlinks des Wiki Artikels '
                     u' „<a href="%s">%s</a>“' % (
                        escape(url_for(page)),
                        escape(page.title)))
    return {
        'page': page
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
                                    syntax tree. Useful for debugging.
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
            page. They all have a proper attachment attributes which is
            an `Attachment`.

        ``form``
            An `AddAttachmentForm` instance.
    """
    page = Page.objects.get_by_name(name)
    if page.rev.attachment_id is not None:
        flash('Anhänge in Anhänge sind nicht erlaubt!')
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
            flash('Hinzufügen des Dateianhangs abgebrochen.')
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
        attachment_name = d.get('filename') or d['attachment'].filename
        filename = d['attachment'].filename or d.get('filename')
        if not attachment_name:
            flash('Bitte gib einen Dateinamen für den Anhang an.')
            return context
        attachment_name = u'%s/%s' % (name, attachment_name)
        attachment_name = normalize_pagename(attachment_name.strip('/'))
        try:
            ap = Page.objects.get_by_name(attachment_name)
        except Page.DoesNotExist:
            ap = None
        if ap is not None and (ap.rev.attachment is None or
                               not d.get('override', False)):
            flash('Es existiert bereits eine Seite oder ein Anhang mit ' +
                  'diesem Namen.')
            return context
        remote_addr = request.META.get('REMOTE_ADDR')
        if ap is None:
            ap = Page.objects.create(user=request.user,
                                     text=d.get('text', u''),
                                     remote_addr=remote_addr,
                                     name=attachment_name,
                                     note=d.get('note', u''),
                                     attachment_filename=filename,
                                     attachment=d['attachment'].content)
        else:
            ap.edit(user=request.user,
                    text=d.get('text', ap.rev.text),
                    remote_addr=remote_addr,
                    note=d.get('note', u''),
                    attachment_filename=filename,
                    attachment=d['attachment'].content)
        attachments = Page.objects.get_attachment_list(name, nocache=True)
        attachments = [Page.objects.get_by_name(i) for i in attachments]
        context['attachments'] = attachments
        flash('Der Dateianhang wurde erfolgreich gespeichert.')
        if ap.metadata.get('weiterleitung'):
            url = href('wiki', ap, redirect='no')
        else:
            url = href('wiki', ap)
        return HttpResponseRedirect(url)
    set_session_info(request, u'verwaltet die Anhänge des Wiki Artikels '
                     u' „<a href="%s">%s</a>“' % (
                        escape(url_for(page)),
                        escape(page.title)))
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
                attachment = d['attachment'].content
                attachment_filename = d['attachment'].filename or \
                                        page.rev.attachment.filename
            page.edit(user=request.user,
                        text=d.get('text', page.rev.text.value),
                        remote_addr=request.META.get('remote_addr'),
                        note=d.get('note', u''),
                        attachment_filename=attachment_filename,
                        attachment=attachment)
            flash('Der Dateianhang wurde erfolgreich bearbeitet.')
            return HttpResponseRedirect(url_for(page))
    return {
        'form': form,
        'page': page
    }

def do_prune(request, name):
    """Clear the page cache."""
    page = Page.objects.get_by_name(name)
    page.prune()
    flash('Der Seitencache wurde geleert.')
    return HttpResponseRedirect(page.get_absolute_url())


@templated('wiki/action_manage.html', modifier=context_modifier)
def do_manage(request, name):
    """
    Show a list of all actions for this page.

    **Template**
        ``'wiki/action_manage.html'``
    """
    return {
        'page':     Page.objects.get_by_name(name)
    }


@simple_check_login
def do_subscribe(request, page_name):
    """
    Subscribe the user to the page with `page_name` or remove him if he is already
    subscribed.
    """
    p = Page.objects.get(name=page_name)
    try:
        s = Subscription.objects.get(user=request.user, wiki_page=p)
    except Subscription.DoesNotExist:
        # there's no such subscription yet, create a new one
        Subscription(user=request.user, wiki_page=p).save()
        flash(u'Du wirst ab jetzt bei Veränderungen dieser Seite benachrichtigt.')
    else:
        # there's already a subscription for this page, remove it
        s.delete()
        flash(u'Du wirst ab nun bei keiner Veränderung mehr benachrichtigt.')
    return HttpResponseRedirect(url_for(p))


PAGE_ACTIONS = {
    'show':         do_show,
    'metaexport':   do_metaexport,
    'log':          do_log,
    'diff':         do_diff,
    'revert':       do_revert,
    'move':         do_move,
    'rename':       do_rename,
    'edit':         do_edit,
    'delete':       do_delete,
    'backlinks':    do_backlinks,
    'export':       do_export,
    'attach':       do_attach,
    'prune':        do_prune,
    'manage':       do_manage,
    'subscribe':    do_subscribe
}
