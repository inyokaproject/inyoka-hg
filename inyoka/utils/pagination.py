# -*- coding: utf-8 -*-
"""
    inyoka.utils.pagination
    ~~~~~~~~~~~~~~~~~~~~~~~

    This file helps creating a pagination. It's able to generate the HTML
    source and to select the right database entries.

    Usage::

        >>> pagination = Pagination(Model.objects.all(),
        ...                         page_number,
        ...                         href('ikhaya'),
        ...                         per_page)
        >>> # the database entries on this page
        >>> objects = pagination.get_objects()
        >>> # the generated HTML code for the pagination
        >>> html = pagination.generate()

    If the page is out of range, it throws a PageNotFound exception.

    :copyright: Copyright 2007 by Armin Ronacher, Benjamin Wiegand.
    :license: GNU GPL.
"""
import math
from django.http import Http404 as PageNotFound


class Pagination(object):

    def __init__(self, query, page, link, per_page=10):
        self.query = query
        self.page = int(page)
        self.link = link
        self.per_page = per_page

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
        total = self.query.count() - 1
        pages = total // self.per_page + 1
        for num in xrange(1, pages + 1):
            if num <= threshold or num > pages - threshold or\
               abs(self.page - num) < math.ceil(threshold / 2.0):
                if result and result[-1] != ellipsis:
                    result.append(commata)
                was_space = False
                if num == 1:
                    link = self.link
                else:
                    link = '%s%d/' % (self.link, num)
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
