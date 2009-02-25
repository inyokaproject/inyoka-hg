# -*- coding: utf-8 -*-
"""
    conftest
    ~~~~~~~~

    Configure the nosetest for our database stuff and other things.

    :copyright: 2009 by Christopher Grebs
    :license: GNU GPL.
"""
import os
import sys
import unittest
from shutil import rmtree
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from nose import util, run
from nose.suite import ContextSuite, ContextSuiteFactory, Test
from nose.loader import TestLoader
from nose.util import log
from nose.config import Config

from inyoka.application import *
from inyoka.conf import settings
from inyoka.utils.cache import set_test_cache


# enable the test environment
set_test_cache()



class InyokaContextSuite(ContextSuite):
    """
    This class just exists to add more features to the test
    context in the future.
    """

    def __init__(self, *args, **kwargs):
        ContextSuite.__init__(self, *args, **kwargs)


class InyokaContextSuiteFactory(ContextSuiteFactory):

    suiteClass = InyokaContextSuite

    def __init__(self, *args, **kwargs):
        ContextSuiteFactory.__init__(self, *args, **kwargs)

    def wrapTests(self, tests):
        log.debug("wrap %s" % tests)
        if callable(tests) or isinstance(tests, unittest.TestSuite):
            log.debug("I won't wrap")
            return tests
        wrapped = []
        for test in tests:
            log.debug("wrapping %s" % test)
            if isinstance(test, Test) or isinstance(test, unittest.TestSuite):
                wrapped.append(test)
            else:
                wrapped.append(Test(test, config=self.config,
                                    resultProxy=self.resultProxy))
        return wrapped



class InyokaTestLoader(TestLoader):

    def __init__(self, config=None, importer=None, workingDir=None,
                 selector=None):
        TestLoader.__init__(self, config, importer, workingDir, selector)
        self.suiteClass = InyokaContextSuiteFactory(config)


def inyoka_suite():
    config = Config()
    config.files = 'setup.cfg'
    config.configure()
    l = InyokaTestLoader(config=config)
    return run(testLoader=l)
