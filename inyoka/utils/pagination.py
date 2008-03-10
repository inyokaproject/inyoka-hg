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
                                    optional_link)
        >>> # the database entries on this page
        >>> objects = pagination.objects
        >>> # the generated HTML code for the pagination
        >>> html = pagination.generate()

    If the page is out of range, it throws a PageNotFound exception.

    Caveat: paginations with link functions generated in a closure are
    not pickleable.

    :copyright: Copyright 2007-2008 by Armin Ronacher, Benjamin Wiegand.
    :license: GNU GPL.
"""
import math
from inyoka.utils.http import PageNotFound
from inyoka.utils.html import escape


class Pagination(object):

    def __init__(self, request, query, page, per_page=10, link=None):
        self.page = int(page)
        self.per_page = per_page

        idx = (self.page - 1) * self.per_page
        result = query[idx:idx + self.per_page]
        if not result and self.page != 1:
            raise PageNotFound()
        self.objects = list(result)

        if isinstance(query, list):
            self.total = len(query)
        else:
            self.total = query.count()

        if link is None:
            link = request.path
        if isinstance(link, basestring):
            self.parameters = {}
            self.link_base = link
        else:
            self.parameters = request.GET
            self.generate_link = link

    def generate_link(self, page, parameters):
        if page == 1:
            return self.link_base
        return '%s%d/' % (self.link_base, page)

    def generate(self, position=None, threshold=2, show_next_link=True):
        normal = u'<a href="%(href)s" class="pageselect">%(page)d</a>'
        active = u'<span class="pageselect active">%(page)d</span>'
        ellipsis = u'<span class="ellipsis"> … </span>'
        was_ellipsis = False
        result = []
        add = result.append
        pages = self.total // self.per_page + 1
        params = self.parameters.copy()
        half_threshold = max(math.ceil(threshold / 2.0), 2)
        for num in xrange(1, pages + 1):
            if num <= threshold or num > pages - threshold or\
               abs(self.page - num) < half_threshold:
                if result and result[-1] != ellipsis:
                    add(u'<span class="comma">, </span>')
                was_space = False
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
                link = escape(self.generate_link(self.page + 1, params))
                tmpl = u'<a href="%s" class="next"> Weiter » </a>'
                add(tmpl % escape(link))
            else:
                add(u'<span class="disabled next"> Weiter » </span>')

        class_ = 'pagination'
        if position:
            class_ += ' pagination_' + position
        return u'<div class="%s">%s<div style="clear: both">' \
               u'</div></div>' % (class_, u''.join(result))
