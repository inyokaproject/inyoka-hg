# -*- coding: utf-8 -*-
"""
    inyoka.utils.database
    ~~~~~~~~~~~~~~~~~~~~~

    This module provides an SQLAlchemy metadata and engine.

    This module must never import application code so that migrations
    can work properly for bootstrapping and upgrading.

    The default session shutdown happens in the application handler in
    `inyoka.application`.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from sqlalchemy import orm
from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import scoped_session, create_session
from sqlalchemy.pool import NullPool
from sqlalchemy.util import to_list
from sqlalchemy.ext.declarative import declarative_base, _declarative_constructor
from inyoka.conf import settings

rdbm = 'mysql'
extra = '?charset=utf8&use_unicode=1'
if 'postgres' in settings.DATABASE_ENGINE:
    rdbm = 'postgres'
    extra = ''

engine = create_engine('%s://%s:%s@%s/%s%s' % (
    rdbm, settings.DATABASE_USER, settings.DATABASE_PASSWORD,
    settings.DATABASE_HOST, settings.DATABASE_NAME, extra
), pool_recycle=25, echo=False,
   poolclass=NullPool)
metadata = MetaData(bind=engine)

session = scoped_session(lambda: create_session(engine,
    autoflush=True, autocommit=False))


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


if settings.DATABASE_DEBUG:
    import logging
    engine_logger = logging.getLogger('sqlalchemy.engine')
    engine_logger.setLevel(logging.INFO)
    engine_logger.addHandler(logging.FileHandler('db.log'))


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
