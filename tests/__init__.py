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

# setup some paths
settings.DATABASE_DEBUG = False
# REQURED! If we're not in DEBUG mode the `TemplateResponse`
# won't have the `tmpl_context` attribute!
settings.DEBUG = True

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
    """
    This is the context for our tests. It provides
    some required things like the `admin` and `user`
    attributes to create a overall test experience.
    """
    admin = None
    user = None

    def __init__(self):
        self.setup_instance()

    def setup_instance(self):
        """
        Setup the test context. That means: Create an admin
        and normal test user.
        """
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
        """Use this method to add a new forum.
        This method will set the right permissions
        for the admin user."""
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

    def open_location(self, path, method='GET', **kwargs):
        """Open a location (url)"""
        resp = self.client.open(path, method=method, base_url=href(self.component), **kwargs)
        return resp

    def get_context(self, path, method='GET', **kwargs):
        """This method returns the internal context of the templates
        so that we can check it in our view-tests."""
        resp = self.open_location(path, method, **kwargs)

        # we assume to test a @templated view function. We don't have that much
        # view functions where we don't use the @templated decorator.
        assert isinstance(resp[0], TemplateResponse)

        return resp[0].tmpl_context


def view(location=None, method='GET', component='portal', **bkw):
    """
    This decorator is used to create an easy test-environment. Example usage::

        @view('/', component='forum')
        def test_forum_index(client, tctx, ctx):
            assert tctx['is_index'] == True

    As you see this decorator adds the following arguments to the function
    call::

        `client`
            The test client. It represents a user's browser. Thanks
            to that the view function is able to create requests and check
            the responses.
        `tctx`
            This is the template context returned by view functions decorated
            with the @templated decorator. So it's required to test a @templated
            function if you use the @view_test decorator.
        `ctx`
            The overall test context. It's a `Context` instance with some methods
            and attributes to ensure a easy test experience.

    :Parameters:
        `location` (optional)
            The script path of the view. E.g ``/forum/foobar/``. If not given
            the `tctx` supplied as an argument of the test-function will be `None`.
        `method`
            The method of the request. It must be one of GET, POST, HEAD, DELETE
            or PUT.
        `component`
            The component of the inyoka portal. E.g portal, forum, paste…
        `bkw`
            You can also use the kwargs for all arguments `werkzeug.test.Client.open`
            uses to supply `data` and other things.
    """
    def _wrapper(func):
        def decorator(*args, **kwargs):
            client = Client(application)
            if not 'follow_redirects' in bkw:
                bkw['follow_redirects'] = True
            if location is not None:
                resp = client.open(location, method=method,
                                   base_url=href(component), **bkw)
                assert isinstance(resp[0], TemplateResponse)
                tctx = resp[0].tmpl_context
            else:
                tctx = None
            args = (client, tctx, context) + args
            return func(*args, **kwargs)
        return patch_wrapper(decorator, func)
    return _wrapper


def run_inyoka_suite():
    import nose.plugins.builtin
    plugins = [x() for x in nose.plugins.builtin.plugins]
    nose.main(plugins=plugins)
    context.teardown_instance()
