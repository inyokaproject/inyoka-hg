# -*- coding: utf-8 -*-
"""
    inyoka.utils.pagination
    ~~~~~~~~~~~~~~~~~~~~~~~

    This file helps creating a pagination.  It's able to generate the HTML
    source and to select the right database entries.

    Usage::

        >>> pagination = Pagination(request,
                                    Model.objects.all(),
        ...                         page_number,
        ...                         per_page,
                                    optional_link,
                                    total=123,
                                    rownum_column=my_table.c.col)
        >>> # the database entries on this page
        >>> objects = pagination.objects
        >>> # the generated HTML code for the pagination
        >>> html = pagination.generate()

    If the page is out of range, it throws a PageNotFound exception.
    You can pass the optional argument `total` if you already know how
    many entries match your query. If you don't, `Pagination` will use
    a database query to find it out.
    For tables that are quite big it's sometimes useful to use an indexed
    column determinating the position instead of using an offset / limit
    statement. In this case you can use the `rownum_column` argument.

    Caveat: paginations with link functions generated in a closure are
    not pickleable.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import math
from inyoka.utils.http import PageNotFound, HttpResponseRedirect
from inyoka.utils.html import escape
from django.utils.encoding import force_unicode
from werkzeug import url_encode



class Pagination(object):

    def __init__(self, request, query, page, per_page=10, link=None,
                 total=None, rownum_column=None):
        self.page = int(page)
        self.per_page = per_page

        idx = (self.page - 1) * self.per_page
        if rownum_column:
            expr = rownum_column.between(idx, idx + self.per_page - 1)
            result = query.filter(expr)
        else:
            result = query[idx:idx + self.per_page]

        self.objects = result

        if total:
            self.total = total
        elif isinstance(query, list):
            self.total = len(query)
        else:
            self.total = query.count()

        if self.per_page == 0: # Display all entries on one page
            self.max_pages = 1
        else:
            self.max_pages = max(0, self.total - 1) // self.per_page + 1

        if self.page > self.max_pages:
            raise PageNotFound()

        if link is None:
            link = request.path
        self.parameters = request.GET
        if isinstance(link, basestring):
            self.link_base = link
        else:
            self.generate_link = link

        self.needs_redirect_to = None
        if self.total and self.total/per_page < 1 and page > 1:
            url = self.generate_link(1, dict(request.GET.lists()))
            self.needs_redirect_to = lambda: HttpResponseRedirect(url)

    def generate_link(self, page, params):
        if page == 1:
            url = self.link_base
        else:
            url = u'%s%d/' % (self.link_base, page)
        return url + (params and u'?' + url_encode(params) or u'')

    def generate(self, position=None, threshold=2, show_next_link=True,
                 show_prev_link=True):
        normal = u'<a href="%(href)s" class="pageselect">%(page)d</a>'
        active = u'<span class="pageselect active">%(page)d</span>'
        ellipsis = u'<span class="ellipsis"> … </span>'
        was_ellipsis = False
        result = []
        add = result.append
        pages = 1
        if self.total:
            pages = max(0, self.total - 1) // self.per_page + 1

        # This unicode/utf-8 conversion exists because of some fancy hacker-bots
        # that try to fuzzy the pagination with some extremly invalid unicode data.
        # Catching those here fixes vulerabilty of the whole application.
        _get_v = lambda v: force_unicode(v).encode('utf-8') if isinstance(v, basestring) else v
        params = dict((force_unicode(k).encode('utf-8'), _get_v(v))
                       for k, v in self.parameters.iteritems())

        half_threshold = max(math.ceil(threshold / 2.0), 2)
        for num in xrange(1, pages + 1):
            if num <= threshold or num > pages - threshold or\
               abs(self.page - num) < half_threshold:
                if result and result[-1] != ellipsis:
                    add(u'<span class="comma">, </span>')
                was_ellipsis = False
                link = self.generate_link(num, params)
                if num == self.page:
                    template = active
                else:
                    template = normal
                add(template % {
                    'href':     escape(link),
                    'page':     num,
                })
            elif not was_ellipsis:
                was_ellipsis = True
                add(ellipsis)

        if show_next_link:
            if self.page < pages:
                link = self.generate_link(self.page + 1, params)
                tmpl = u'<a href="%s" class="next">Weiter »</a>'
                add(tmpl % escape(link))
            else:
                add(u'<span class="disabled next">Weiter »</span>')

        if show_prev_link:
            if self.page > 1:
                link = self.generate_link(self.page -1, params)
                tmpl = u'<a href="%s" class="prev">« Zurück</a>'
                result.insert(0, tmpl % escape(link))
            else:
                result.insert(0, (u'<span class="disabled prev">« Zurück</span>'))

        class_ = 'pagination'
        if position:
            class_ += ' pagination_' + position
        return u'<div class="%s">%s<div style="clear: both">' \
               u'</div></div>' % (class_, u''.join(result))
