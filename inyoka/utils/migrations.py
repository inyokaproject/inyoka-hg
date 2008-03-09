# -*- coding: utf-8 -*-
"""
    inyoka.utils.migrations
    ~~~~~~~~~~~~~~~~~~~~~~~

    This module provides the implementation for our migration
    definitions in `inyoka.migrations`.

    This module must never import application code so that migrations
    can work properly for bootstrapping and upgrading.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import sys
from inspect import getdoc
from sqlalchemy import Table
from inyoka.utils.database import metadata, engine


class Migrations(object):

    def __init__(self, migrations):
        self.metadata = metadata
        self.engine = engine
        self.migrations = migrations
        self.schema_version = 0

        # try to get the schema version.  If not possible we don't have
        # a schema yet and thus version 0
        try:
            info_table = Table('__migration_info__', metadata,
                                    autoload=True)
            row = info_table.select().execute().fetchone()
            if row:
                self.schema_version = row.schema_version
        except:
            pass

    def __getitem__(self, name):
        """Return the table with the given name."""
        return Table(name, metadata)

    def upgrade(self):
        # get the migrations we want to perform
        migrate = self.migrations[self.schema_version:]
        version = self.schema_version

        if not migrate:
            print >> sys.stderr, 'nothing to migrate.'
            print >> sys.stderr, 'current schema version:', version
            return

        # perform the migrations and print to stdout
        for migration in migrate:
            migration(self)
            version += 1
            print >> sys.stderr, 'upgraded to %d (%r)' % (
                version,
                migration.__name__,
            )
            for line in (getdoc(migration) or '').splitlines():
                print >> sys.stderr, '    |', line
            print >> sys.stderr

        # update migration table
        self.engine.execute('update __migration_info__ set '
                            'schema_version = %s;', [version])
        self.schema_version = version

        print >> sys.stderr, 'new schema version:', version
