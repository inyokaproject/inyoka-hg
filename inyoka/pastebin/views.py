# -*- coding: utf-8 -*-
"""
    inyoka.pastebin.views
    ~~~~~~~~~~~~~~~~~~~~~

    Views for the pastebin.

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
from datetime import datetime
from inyoka.utils.urls import global_not_found
from inyoka.utils.urls import href, url_for
from inyoka.utils.sessions import set_session_info
from inyoka.utils.http import templated, HttpResponseRedirect, HttpResponse, \
        PageNotFound
from inyoka.utils.pagination import Pagination
from inyoka.utils.flashing import flash
from inyoka.pastebin.forms import AddPasteForm
from inyoka.pastebin.models import Entry


def not_found(request, err_message=None):
    """
    Displayed if a url does not match or a view tries to display a not
    exising resource.
    """
    return global_not_found(request, 'pastebin', err_message)


@templated('pastebin/add.html')
def index(request):
    if request.method == 'POST':
        form = AddPasteForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            entry = Entry(title=data['title'] or 'Unbenannt',
                          author=request.user,
                          lang=data['language'], code=data['code'],
                          pub_date=datetime.utcnow())
            entry.save()
            flash(u'Dein Eintrag wurde erfolgreich gespeichert. Du kannst '
                  u'folgenden Code verwenden, um ihn einzubinden: '
                  u'<code>[paste:%s:%s]</code>' % (entry.id, entry.title),
                  True)
            return HttpResponseRedirect(href('pastebin', entry.id))
    else:
        form = AddPasteForm()
    set_session_info(request, u'erstellt gerade ein neues Paste.',
                     'Paste')
    return {
        'form': form,
        'page': 'add'
    }


@templated('pastebin/display.html')
def display(request, entry_id):
    try:
        entry = Entry.objects.get(id=entry_id)
    except Entry.DoesNotExist:
        return not_found(request, u'Paste Nummer %s konnte nicht gefunden '
                                  u'werden' % entry_id)
    referrer = request.META.get('HTTP_REFERER')
    if referrer and entry.add_referrer(referrer):
        entry.save()
    set_session_info(request,
        u'schaut sich Paste-Eintrag <a href="%s">%s</a> an.' % (
            url_for(entry),
            entry.title or entry.id),
        u'besuche den Eintrag'
    )
    return {
        'entry': entry,
        'page':  'browse'
    }


def raw(request, entry_id):
    try:
        entry = Entry.objects.get(id=entry_id)
    except Entry.DoesNotExist:
        raise PageNotFound
    return HttpResponse(entry.code, content_type='text/plain')


@templated('pastebin/browse.html')
def browse(request):
    set_session_info(request, u'schaut sich die Paste-Liste an.',
                     'Paste-Liste')
    return {
        'entries':      list(Entry.objects.limit(50)),
        'page':         'browse'
    }
