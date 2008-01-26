"""
    inyoka.utils.djangoext
    ~~~~~~~~~~~~~~~~~~~~~~

    Various extension for django.

    :copyright: 2007 by Christoph Hack.
    :license: GNU GPL.
"""
from django.db.models.fields import Field
from django.db import get_creation_module


class BinaryField(Field):
    """
    A binary field (BLOB) for the django database.
    """

    def __init__(self, *args, **kwargs):
        Field.__init__(self, *args, **kwargs)

    def db_type(self):
        creation_db = get_creation_module().__name__.split('.')
        if 'ado_mssql' in creation_db:
            return 'varbinary(%(maxlength)s)' % self.__dict__
        if 'sqlite3' in creation_db:
            return 'BLOB' % self.__dict__
        if 'postgresql_psycopg2' in creation_db or 'postgresql' in creation_db:
            return 'bytea' % self.__dict__
        if 'mysql' in creation_db:
            return 'BLOB' % self.__dict__

