# -*- coding: utf-8 -*-
"""
    conftest
    ~~~~~~~~

    Configure py.test for support stuff.

    :copyright: 2007 by Armin Ronacher.
    :license: GNU GPL.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import py
from django.conf import settings
from inyoka import default_settings

test_settings = {}
for key, value in default_settings.__dict__.iteritems():
    if key.isupper():
        test_settings[key] = value

test_settings.update(
    TEST_DATABASE_CHARSET='utf8',
    TEST_DATABASE_COLLATION='utf8_unicode_ci',
    TEST_DATABASE_NAME='ubuntuusers_test',
    DATABASE_USER='root',
    XAPIAN_DATABASE='/tmp/ubuntuusers_test.xapdb',
    BASE_DOMAIN_NAME='test.ubuntuusers.de',
    SESSION_COOKIE_DOMAIN='.test.ubuntuusers.de',
    MEDIA_URL='http://media.test.ubuntuusers.de',
    STATIC_URL='http://static.test.ubuntuusers.de',
    ADMIN_MEDIA_PREFIX = 'http://static.test.ubuntuusers.de/_admin/',
    INYOKA_SYSTEM_USER_EMAIL = 'system@test.ubuntuusers.de'
)
settings.configure(**test_settings)

from django.test.utils import create_test_db, destroy_test_db
from inyoka.utils.search import search
from inyoka.portal.user import User
from shutil import rmtree


class Directory(py.test.collect.Directory):

    def setup(self):
        create_test_db(False, True)
        # create a basic admin user for testing the user models
        User.objects.register_user('admin', 'admin@example.org', 'default', False)
        search.get_connection(True)

    def teardown(self):
        try:
            rmtree(settings.XAPIAN_DATABASE)
        except:
            pass
        destroy_test_db(None, False)


class Module(py.test.collect.Module):

    def makeitem(self, name, obj, usefilters=True):
        if name.startswith('test_'):
            if hasattr(obj, 'func_code'):
                return TestFunction(name, parent=self)
            elif isinstance(obj, basestring):
                return DocTest(name, parent=self)


class TestFunction(py.test.collect.Function):

    def execute(self, target, *args):
        co = target.func_code
        target(*args)


class DocTest(py.test.collect.Item):

    def run(self):
        mod = py.std.types.ModuleType(self.name)
        mod.__doc__ = self.obj
        self.execute(mod)

    def execute(self, mod):
        mod.MODULE = self.parent.obj
        failed, tot = py.compat.doctest.testmod(mod, verbose=True)
        if failed:
            py.test.fail('doctest %s: %s failed out of %s' % (
                         self.fspath, failed, tot))
