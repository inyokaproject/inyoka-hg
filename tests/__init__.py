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
import urlparse
import nose
import unittest
import tests
from werkzeug import Client, BaseResponse
from nose.plugins.base import Plugin
from inyoka.conf import settings

settings.DATABASE_DEBUG = False
dbname = os.environ.get('INYOKA_TEST_DATABASE', 'inyoka_test')
settings.DATABASE_NAME = dbname
instance_dir = os.tempnam()
settings.MEDIA_ROOT = os.path.join(instance_dir, 'media')
os.mkdir(instance_dir)

# now run the migrations
from inyoka.utils.migrations import Migrations
from inyoka.migrations import MIGRATIONS
Migrations(MIGRATIONS).upgrade()
from inyoka.utils.database import metadata
metadata.clear()

from inyoka.application import application
from inyoka.utils import create_media_folders
from inyoka.utils.cache import set_test_cache
from inyoka.utils.urls import href
from inyoka.utils.http import TemplateResponse
from inyoka.portal.user import User, PERMISSION_NAMES
from inyoka.forum.models import Forum, Privilege
from inyoka.forum.acl import PRIVILEGES_DETAILS, join_flags
from inyoka.utils.database import session
from inyoka.utils.decorators import patch_wrapper


# enable the test environment
set_test_cache()

# create static folders
create_media_folders(instance_dir)


class Context(object):
    admin = None
    user = None

    def __init__(self):
        self.setup_instance()

    def setup_instance(self):
        # create admin user
        if not User.objects.get(username='admin'):
            self.admin = admin = User.objects.register_user('admin', 'admin@ubuntuusers.de', 'admin', False)
            permissions = 0
            for perm in PERMISSION_NAMES.keys():
                permissions |= perm
            admin._permissions = permissions
            admin.save()
            bits = dict(PRIVILEGES_DETAILS).keys()
            bits = join_flags(*bits)
            # maybe there are some forums :-)
            for forum in Forum.query.all():
                self.add_forum(forum)

        # create the test user
        if not User.objects.get(username='test'):
            self.user = user = User.objects.register_user('test', 'test@ubuntuusers.de', 'test', False)
        return instance_dir

    def add_forum(self, forum):
        bits = dict(PRIVILEGES_DETAILS).keys()
        bits = join_flags(*bits)
        privilege = Privilege(
            user=self.admin,
            forum=forum,
            positive=bits,
            negative=0
        )
        session.save(privilege)
        session.commit()
        session.flush()

    def teardown_instance(self):
        session.rollback()
        session.clear()
        metadata.drop_all()

context = Context()


class ViewTestCase(unittest.TestCase):

    component = 'portal'

    def setUp(self):
        self.client = Client(application)

    def open_location(self, path, method='GET', follow_redirects=True):
        resp = self.client.open(path, method=method, base_url=href(self.component), follow_redirects=True)
        return resp

    def get_context(self, path, method='GET'):
        resp = self.open_location(path, method)

        # we assume to test a @templated view function. We don't have that much
        # view functions where we don't use the @templated decorator.
        assert isinstance(resp[0], TemplateResponse)

        return resp[0].tmpl_context


def view_test(location=None, method='GET', component='portal'):
    def _wrapper(func):
        def decorator(*args, **kwargs):
            client = Client(application)
            resp = client.open(location, method=method, base_url=href(component), follow_redirects=True)
            assert isinstance(resp[0], TemplateResponse)
            args = (client, resp[0].tmpl_context, context) + args
            return func(*args, **kwargs)
        return patch_wrapper(decorator, func)
    return _wrapper


def run_inyoka_suite():
    import nose.plugins.builtin
    plugins = [x() for x in nose.plugins.builtin.plugins]
    nose.main(plugins=plugins)
    context.teardown_instance()
