# -*- coding: utf-8 -*-
"""
    conftest
    ~~~~~~~~

    Configure py.test for support stuff.  No database support right now!

    :copyright: 2007-2008 by Armin Ronacher.
    :license: GNU GPL.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import py
from inyoka.conf import settings

from inyoka.utils.cache import set_test_cache
from shutil import rmtree


# enable the test environment
set_test_cache()


class Directory(py.test.collect.Directory):
    pass


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
