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
import nose
import tests
from inyoka.application import *
from inyoka.conf import settings
from inyoka.utils.cache import set_test_cache

# enable the test environment
set_test_cache()


def run_inyoka_suite():
    nose.main(plugins=[])
