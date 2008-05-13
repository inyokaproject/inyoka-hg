# -*- coding: utf-8 -*-
"""
    inyoka.utils.sortable
    ~~~~~~~~~~~~~~~~~~~~~

    This file helps creating a sortable Table.

    You can create a new instance of `Sortable` this way::

        >>> table = Sortable(objects, args, default)

    :Parameters:
        objects
            This has to be a django database query set that should be sorted.
            Use the `get_objects()` to get it back in the right order.
        args
            The GET arguments (request.args).
        default
            Defines the default sorting mode.

    Every instance of `Sortable` has these methods:

        - get_html:
            Returns a HTML link for sorting the table.
            This function is usually called inside the template.

            :Parameters:
                key
                    The name of the database column that should be used for
                    sorting.
                value
                    The name that is displayed for the link.

        - get_objects:
            Returns an ordered database query set.

    A working example of a box would look like this:
    Inside Python File::

        from inyoka.utils.sortable import Sortable
        from inyoka.portal.user import User

        @templated('portal/memberlist.html')
        def memberlist(req):
            table = Sortable(User.objects.all(), req.GET, 'id')
            return {
                'users': list(table.get_objects()),
                'table': table
            }

    Inside the template file::

        <tr>
          <th>
            {{ table.get_html('id', '#') }}
          </th>
          <th>
            {{ table.get_html('username', 'Benutzername') }}
          </th>
        </tr>
        {% for user in users %}
          (...)
        {% endfor %}

    Hint: Because Django and SQLAlchemy query objects are somewhat different
    there is a small workaround for our forum.
    Use `sqlalchemy=True` along with `sa_column=my_sa.c.column`
    to tell the `Sortable` that it should shift into sqlalchemy-mode.

    :copyright: 2007-2008 by Benjamin Wiegand, Christopher Grebs.
    :license: GNU GPL, see LICENSE for more details.
"""
from inyoka.utils.urls import href
from inyoka.utils.templating import render_template


class Sortable(object):

    def __init__(self, objects, args, default, sqlalchemy=False,
                 sa_column=None):
        self.objects = objects
        self.order = args.get('order') or default
        self.order_column = self.order.startswith('-') and self.order[1:] or \
                            self.order
        self.sa_column = sa_column
        self.related = args.get('related') or False
        self.default = default
        self.is_sqlalchemy = sqlalchemy

    def get_html(self, key, value, related=False):
        if key == self.order_column:
            new_order = '%s%s' % (
                not self.order.startswith('-') and '-' or '',
                self.order_column
            )
            img = '<img src="%s" alt="" />' % href('static', 'img',
                '%s.png' % (self.order.startswith('-') and 'down' or 'up'))
        else:
            new_order = key
            img = ''
        related_q = ''
        if related:
            related_q = '&related=%s' % (related or self.related)
        return '<a href="?order=%s%s">%s</a>%s' % (
            new_order, related_q, value, img)

    def get_objects(self):
        order = self.order
        if self.related:
            if self.is_sqlalchemy:
                return self.objects.order_by(order)
            else:
                return self.objects.order_by(order).select_related()
        return self.objects.order_by(order)


ACTIONS = {
    'str': {
        'is':           u'ist gleich',
        'contains':     u'enthält',
        'startswith':   u'beginnt mit',
    },
    'int': {
        'is':           u'ist gleich',
        'greater':      u'ist größer als',
        'lower':        u'ist kleiner als',
    },
    'date': {
        'is':           u'ist gleich',
        'greater':      u'ist später als',
        'lower':        u'ist früher als',
    }
}
ACTIONS_MAP = {
    'is':         lambda f, v: f == v,
    'contains':   lambda f, v: f.contains(v),
    'startswith': lambda f, v: f.startswith(v),
    'greater':    lambda f, v: f > v,
    'lower':      lambda f, v: f < v,
    'bool':       lambda f, v: f == (v == 'true'),
}


class Filterable(object):
    def __init__(self, model, objects, fields, args):
        self.model = model
        self.fields = fields
        self.objects = objects
        self.args = args
        self.filters = {}
        for field in fields:
            action = args.get('%s_action' % field)
            value = args.get('%s_value' % field)
            if action and value and action in ACTIONS_MAP \
               and not field == args.get('remove_filter'):
                self.filters[field] = action, value
        new_filter = args.get('new_filter')
        if 'add_filter' in args and new_filter and new_filter in fields:
            self.filters[new_filter] = 'is', ''


    def get_html(self):
        return render_template('utils/filterable.html', {
            'filters': self.filters,
            'fields':  self.fields,
            'actions': ACTIONS,
            'args':    {'order': self.args.get('order')}
        })

    def get_objects(self):
        for field, filter in self.filters.iteritems():
            action, value = filter
            if value:
                self.objects = self.objects.filter(
                    ACTIONS_MAP[action](getattr(self.model, field), value)
                )
        return self.objects
