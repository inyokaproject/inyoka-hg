# -*- coding: utf-8 -*-
"""
    inyoka.utils.database
    ~~~~~~~~~~~~~~~~~~~~~

    This module provides an SQLAlchemy metadata and engine.

    The default session shutdown happens in the application handler in
    `inyoka.application`.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from __future__ import with_statement
import sys
import time
from types import ModuleType
from threading import Lock
import sqlalchemy
from sqlalchemy import orm, sql, exc
from sqlalchemy import MetaData, create_engine, String, Unicode
from sqlalchemy.orm import scoped_session, create_session
from sqlalchemy.pool import NullPool
from sqlalchemy.util import to_list
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.attributes import get_attribute, set_attribute
from sqlalchemy.interfaces import ConnectionProxy
from sqlalchemy.orm.session import Session as SASession
from sqlalchemy.orm.interfaces import AttributeExtension
from inyoka.conf import settings
from inyoka.utils.text import get_next_increment, slugify
from inyoka.utils.collections import flatten_iterator
from inyoka.utils.debug import find_calling_context
from inyoka.utils.local import current_request



_engine = None
_engine_lock = Lock()


def get_engine():
    """Creates the engine if it does not exist and returns
    the current engine.
    """
    global _engine
    with _engine_lock:
        if _engine is None:
            rdbm = 'mysql'
            extra = '?charset=utf8&use_unicode=1'
            if 'postgresql' in settings.DATABASE_ENGINE:
                rdbm = 'postgresql+psycopg2'
                extra = ''

            options = {}
            if settings.DEBUG:
                options['proxy'] = ConnectionDebugProxy()

            #XXX: We don't use a connection pool because of fancy mysql
            #     timeout settings on the ubuntu-eu servers so that
            #     our php applications don't kill the server with open
            #     connections.
            _engine = create_engine('%s://%s:%s@%s/%s%s' % (
                rdbm, settings.DATABASE_USER, settings.DATABASE_PASSWORD,
                settings.DATABASE_HOST, settings.DATABASE_NAME, extra
            ), pool_recycle=25, echo=False, poolclass=NullPool, **options)

        return _engine


class InyokaSession(SASession):
    """Session that binds the engine as late as possible"""

    def __init__(self):
        SASession.__init__(self, get_engine(), autoflush=True,
                           autocommit=False)


metadata = MetaData()
session = orm.scoped_session(InyokaSession)


def refresh_engine():
    """Gets rid of the existing engine.  Useful for unittesting, use with care.
    Do not call this function if there are multiple threads accessing the
    engine.  Only do that in single-threaded test environments or console
    sessions.
    """
    global _engine
    with _engine_lock:
        session.remove()
        if _engine is not None:
            _engine.dispose()
        _engine = None


def atomic_add(obj, column, delta, expire=False, primary_key_field=None):
    """Performs an atomic add (or subtract) of the given column on the
    object.  This updates the object in place for reflection but does
    the real add on the server to avoid race conditions.  This assumes
    that the database's '+' operation is atomic.

    If `expire` is set to `True`, the value is expired and reloaded instead
    of added of the local value.  This is a good idea if the value should
    be used for reflection. The `primary_key_field` should only get passed in,
    if the mapped table is a join between two tables.
    """
    obj_mapper = orm.object_mapper(obj)
    primary_key = obj_mapper.primary_key_from_instance(obj)
    assert len(primary_key) == 1, 'atomic_add not supported for '\
        'classes with more than one primary key'

    table = obj_mapper.columns[column].table

    if primary_key_field:
        assert table.c[primary_key_field].primary_key == True, 'no primary key field'

    primary_key_field = table.c[primary_key_field] if primary_key_field is not None \
                         else obj_mapper.primary_key[0]
    stmt = sql.update(table, primary_key_field == primary_key[0], {
        column:     table.c[column] + delta
    })
    get_engine().execute(stmt)

    val = orm.attributes.get_attribute(obj, column)
    if expire:
        orm.attributes.instance_state(obj).expire_attributes(
            orm.attributes.instance_dict(obj), [column])
    else:
        orm.attributes.set_committed_value(obj, column, val + delta)


class ConnectionDebugProxy(ConnectionProxy):
    """Helps debugging the database."""

    def cursor_execute(self, execute, cursor, statement, parameters,
                       context, executemany):
        start = time.time()
        try:
            return execute(cursor, statement, parameters, context)
        finally:
            if current_request:
                request = current_request._get_current_object()
                if request is not None:
                    request.queries.append((statement, parameters, start,
                                            time.time(), find_calling_context()))


def mapper(model, table, **options):
    """A mapper that hooks in standard extensions."""
    extensions = to_list(options.pop('extension', None), [])
    options['extension'] = extensions
    # automatically register the model to the session
    old_init = getattr(model, '__init__', lambda s: None)
    def register_init(self, *args, **kwargs):
        old_init(self, *args, **kwargs)
        session.add(self)
    model.__init__ = register_init
    return orm.mapper(model, table, **options)


class Query(orm.Query):
    """Default query class."""

    def cached(self, key, timeout=None):
        """Return a query result from the cache or execute the query again"""
        from inyoka.utils.cache import cache
        data = cache.get(key)
        if data is None:
            data = self.all()
            cache.set(key, data, timeout=timeout)
        data = list(self.merge_result(data, load=False))
        return data

    def lightweight(self, deferred=None, lazy=None):
        """Send a lightweight query which deferes some more expensive
        things such as comment queries or even text and parser data.
        """
        args = map(db.lazyload, lazy or ()) + map(db.defer, deferred or ())
        return self.options(*args)


class ModelBase(object):
    """Internal baseclass for all models.  It provides some syntactic
    sugar and maps the default query property.

    We use the declarative model api from sqlalchemy.
    """

    def __eq__(self, other):
        equal = True
        if type(other) != type(self):
            return False
        for key in type(self)._sa_class_manager.mapper.columns.keys():
            if getattr(self, key) != getattr(other, key):
                equal = False
                break
        return equal

    def __repr__(self):
        attrs = []
        dict_ = type(self)._sa_class_manager.mapper.columns.keys()
        for key in dict_:
            if not key.startswith('_'):
                attrs.append((key, getattr(self, key)))
        return self.__class__.__name__ + '(' + ', '.join(x[0] + '=' +
                                            repr(x[1]) for x in attrs) + ')'


# configure the declarative base
Model = declarative_base(name='Model', cls=ModelBase,
    mapper=mapper, metadata=metadata)
Model.query = session.query_property(Query)


class SlugGenerator(orm.MapperExtension):
    """This MapperExtension can generate unique slugs automatically.

    .. note::

        If you apply a max_length to the slug field that length is
        decreased by 10 to get enough space for increment strings.

    :param slugfield: The field the slug gets saved to.
    :param generate_from: Either a string or a list of fields to generate
                          the slug from.  If a list is applied they are
                          joined with ``sep``.
    :param sep: The string to join multiple fields.  If only one field applied
                the seperator is not used.
    """

    def __init__(self, slugfield, generate_from, sep=u'/'):
        if not isinstance(generate_from, (list, tuple)):
            generate_from = (generate_from,)
        self.slugfield = slugfield
        self.generate_from = generate_from
        self.separator = sep

    def before_insert(self, mapper, connection, instance):
        fields = [get_attribute(instance, f) for f in self.generate_from]

        table = mapper.columns[self.slugfield].table
        column = table.c[self.slugfield]
        assert isinstance(column.type, (Unicode, String))
        max_length = column.type.length

        # filter out fields with no value as we cannot join them they are
        # not relevant for slug generation.
        fields = filter(None, fields)
        slug = self.separator.join(map(slugify, fields))
        # strip the string if max_length is applied
        slug = slug[:max_length-10] if max_length is not None else slug

        set_attribute(instance, self.slugfield,
            find_next_increment(getattr(instance.__class__, self.slugfield),
                                slug, max_length))
        return orm.EXT_CONTINUE


def select_blocks(query, pk, block_size=1000, start_with=0, max_fails=10):
    """Execute a query blockwise to prevent lack of ram"""
    range = (start_with, start_with + block_size)
    failed = 0
    while failed < max_fails:
        result = query.where(pk.between(*range)).execute()
        i = 0
        for i, row in enumerate(result):
            yield row
        if i == 0:
            failed += 1
        else:
            failed = 0
        range = range[1] + 1, range[1] + block_size


def find_next_increment(column, string, max_length=None):
    """Get the next incremented string based on `column` and `string`.

    Example::

        find_next_increment(Category.slug, 'category name')
    """
    existing = session.query(column).filter(column.like('%s%%' % string)).all()
    return get_next_increment(flatten_iterator(existing), string, max_length)


def _make_module():
    db = ModuleType('db')
    for mod in sqlalchemy, orm:
        for key, value in mod.__dict__.iteritems():
            if key in mod.__all__:
                setattr(db, key, value)

    # support for postgresql array type
    from sqlalchemy.dialects.postgresql.base import PGArray
    db.PGArray = PGArray

    db.get_engine = get_engine
    db.session = session
    db.metadata = metadata
    db.mapper = mapper
    db.atomic_add = atomic_add
    db.find_next_increment = find_next_increment
    db.Model = Model
    db.Query = Query
    db.SlugGenerator = SlugGenerator
    db.AttributeExtension = AttributeExtension
    db.ColumnProperty = orm.ColumnProperty
    db.NoResultFound = orm.exc.NoResultFound
    db.SQLAlchemyError = exc.SQLAlchemyError
    return db

sys.modules['inyoka.core.database.db'] = db = _make_module()
