# -*- coding: utf-8 -*-
"""
    inyoka.pastebin.views
    ~~~~~~~~~~~~~~~~~~~~~

    Views for the pastebin.

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
from datetime import datetime
from django.http import HttpResponseRedirect, HttpResponse
from inyoka.portal.views import not_found
from inyoka.pastebin.forms import AddPasteForm
from inyoka.pastebin.models import Entry
from inyoka.utils.urls import href, url_for
from inyoka.utils.sessions import set_session_info
from inyoka.utils.http import templated
from inyoka.utils.pagination import Pagination
from inyoka.utils.decorators import simple_check_login


@simple_check_login
@templated('pastebin/add.html')
def index(request):
    if request.method == 'POST':
        form = AddPasteForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            entry = Entry(title=data['title'] or 'Unbenannt',
                          author=request.user,
                          lang=data['language'], code=data['code'],
                          pub_date=datetime.now())
            entry.save()
            return HttpResponseRedirect(href('pastebin', entry.id))
    else:
        form = AddPasteForm()
    set_session_info(request, u'erstellt gerade ein neues Paste.',
                     'Paste')
    return {
        'form': form
    }


@templated('pastebin/display.html')
def display(request, entry_id):
    try:
        entry = Entry.objects.get(id=entry_id)
    except Entry.DoesNotExist:
        return not_found(request, 'Paste Nummer %s konnte nicht gefunden werden'
                         % entry_id)
    referrer = request.META.get('HTTP_REFERER')
    if referrer and entry.add_referrer(referrer):
        entry.save()
    set_session_info(request,
        u'schaut sich Paste-Eintrag <a href="%s">%s</a> an.' % (
            url_for(entry),
            entry.title or entry.id),
        'besuche den Eintrag'
    )
    return {
        'entry': entry,
    }


def raw(request, entry_id):
    entry = Entry.objects.get(id=entry_id)
    return HttpResponse(entry.code, content_type='text/plain')


@templated('pastebin/browse.html')
def browse(request, page=1):
    pagination = Pagination(request, Entry.objects.all(), page)
    set_session_info(request, u'schaut sich die Paste-Liste an.',
                     'Paste-Liste')
    return {
        'entries':      list(pagination.get_objects()),
        'pagination':   pagination.generate()
    }
