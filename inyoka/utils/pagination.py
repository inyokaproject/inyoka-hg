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
        >>> objects = pagination.get_objects()
        >>> # the generated HTML code for the pagination
        >>> html = pagination.generate()

    If the page is out of range, it throws a PageNotFound exception.

    :copyright: Copyright 2007 by Armin Ronacher, Benjamin Wiegand.
    :license: GNU GPL.
"""
import math
from inyoka.utils.http import PageNotFound


class Pagination(object):

    def __init__(self, request, query, page, per_page=10, link=None):
        self.query = query
        self.page = int(page)
        self.per_page = per_page
        self.parameters = request.GET

        if link is None:
            link_base = request.path
        elif not isinstance(link, basestring):
            self.link_func = link
            return
        else:
            link_base = link or request.path

        def link_func(page, parameters):
            if page == 1:
                rv = link_base
            else:
                rv = '%s%d/' % (link_base, page)
            if parameters:
                rv += '?' + parameters.urlencode()
            return rv
        self.link_func = link_func

    def get_objects(self):
        idx = (self.page - 1) * self.per_page
        result = self.query[idx:idx + self.per_page]
        if not result and self.page != 1:
            raise PageNotFound()
        return result

    def generate(self, normal='<a href="%(href)s">%(page)d</a>',
                 active='<strong>%(page)d</strong>',
                 commata=',\n',
                 ellipsis=' ...\n',
                 threshold=3):
        was_ellipsis = False
        result = []
        if isinstance(self.query, list):
            total = len(self.query)
        else:
            total = self.query.count() - 1
        pages = total // self.per_page + 1
        params = self.parameters.copy()
        for num in xrange(1, pages + 1):
            if num <= threshold or num > pages - threshold or\
               abs(self.page - num) < math.ceil(threshold / 2.0):
                if result and result[-1] != ellipsis:
                    result.append(commata)
                was_space = False
                link = self.link_func(num, params)
                if num == self.page:
                    template = active
                else:
                    template = normal
                result.append(template % {
                    'href':     link,
                    'page':     num,
                })
            elif not was_ellipsis:
                was_ellipsis = True
                result.append(ellipsis)

        return ''.join(result)
