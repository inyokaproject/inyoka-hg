# -*- coding: utf-8 -*-
"""
    inyoka.planet.views
    ~~~~~~~~~~~~~~~~~~~

    Views for the planet.

    :copyright: 2007 by Benjamin Wiegand, Marian Sigler.
    :license: GNU GPL, see LICENSE for more details.
"""
from django.utils.text import truncate_html_words
from inyoka.conf import settings
from inyoka.portal.user import Group
from inyoka.portal.utils import check_login
from inyoka.utils.urls import href
from inyoka.utils.sessions import set_session_info
from inyoka.utils.http import PageNotFound, templated, \
     HttpResponseRedirect, HttpResponse
from inyoka.utils.html import escape
from inyoka.utils.flashing import flash
from inyoka.utils.templating import render_template
from inyoka.utils.pagination import Pagination
from inyoka.utils.mail import send_mail
from inyoka.utils.cache import cache
from inyoka.utils.dates import group_by_day
from inyoka.utils.urls import global_not_found
from inyoka.planet.models import Blog, Entry
from inyoka.planet.forms import SuggestBlogForm
from inyoka.utils.feeds import FeedBuilder


def not_found(request, err_message=None):
    """
    Displayed if a url does not match or a view tries to display a not
    exising resource.
    """
    return global_not_found(request, 'planet', err_message)


def context_modifier(request, context):
    """
    This function is called of ``templated`` automatically to copy the list of
    blogs into the context.
    """
    context['blogs'] = list(Blog.objects.all())


@templated('planet/index.html', modifier=context_modifier)
def index(request, page=1):
    """
    The index function just returns the 30 latest entries of the planet.
    The page number is optional.
    """
    pagination = Pagination(request, Entry.objects.all(), page, 30)
    set_session_info(request, u'betrachtet den <a href="%s">Planeten</a>' %
                     href('planet'), 'Planet')
    return {
        'days':         group_by_day(pagination.objects),
        'pagination':   pagination
    }


@check_login(message=u'Du musst eingeloggt sein, um einen Blog'
                     u' vorzuschlagen.')
@templated('planet/suggest.html', modifier=context_modifier)
def suggest(request):
    """
    A Page to suggest a new blog.  It just sends an email to the planet
    administrators.
    """
    if 'abort' in request.POST:
        return HttpResponseRedirect(href('planet'))

    if request.method == 'POST':
        form = SuggestBlogForm(request.POST)
        if form.is_valid():
            ikhaya_group = Group.objects.get(id=settings.IKHAYA_GROUP_ID)
            users = ikhaya_group.user_set.all()
            text = render_template('mails/planet_suggest.txt',
                                   form.cleaned_data)
            send_mail('Neuer Blogvorschlag', text,
                      settings.INYOKA_SYSTEM_USER_EMAIL,
                      [u.email for u in users])
            if not users:
                flash(u'Es sind keine Benutzer als Planet-Administratoren '\
                      u'eingetragen', False)
                return HttpResponseRedirect(href('planet'))
            flash(u'Der Blog „%s“ wurde vorgeschlagen.' %
                  escape(form.cleaned_data['name']), True)
            return HttpResponseRedirect(href('planet'))
    else:
        form = SuggestBlogForm()
    return {
        'form':         form
    }


def feed(request, mode='short', count=20):
    """show the feeds for the planet"""

    if not mode in ('full', 'short', 'title'):
        raise PageNotFound

    count = int(count)
    if count not in (10, 20, 30, 50, 75, 100):
        raise PageNotFound

    key = 'planet/feeds/%s/%d' % (mode, count)
    content = cache.get(key)
    if content is not None:
        content_type='application/atom+xml; charset=utf-8'
        return HttpResponse(content, content_type=content_type)

    feed = FeedBuilder(
        title=u'ubuntuusers Planet',
        url=href('planet'),
        feed_url=request.build_absolute_uri(),
        id=href('planet'),
        subtitle=u'Der ubuntuusers-Planet sammelt verschiedene Blogs zu '
                 u'Ubuntu und Linux',
        rights=href('portal', 'lizenz'),
    )

    for entry in Entry.objects.all()[:count]:
        kwargs = {}
        if mode == 'full':
            kwargs['content'] = u'<div xmlns="http://www.w3.org/1999/' \
                                u'xhtml">%s</div>' % entry.text
            kwargs['content_type'] = 'xhtml'
        if mode == 'short':
            summary = truncate_html_words(entry.text, 100)
            kwargs['summary'] = u'<div xmlns="http://www.w3.org/1999/' \
                                u'xhtml">%s</div>' % summary
            kwargs['content_type'] = 'xhtml'
        if entry.author_homepage:
            kwargs['author'] = {
                'name': entry.author,
                'uri':  entry.author_homepage
            }
        else:
            kwargs['author'] = entry.author

        feed.add(
            title=entry.title,
            url=entry.url,
            id=entry.guid,
            updated=entry.updated,
            published=entry.pub_date,
            **kwargs
        )

    response = feed.get_atom_response()
    cache.set(key, response.content, 600)
    return response
