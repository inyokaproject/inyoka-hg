#-*- coding: utf-8 -*-
"""
    test__user
    ~~~~~~~~~~

    Some tests for our user model.

    :copyright: 2009 by Florian Apolloner.
    :license: GNU GPL.
"""
import unittest
from StringIO import StringIO

from inyoka.portal.user import *
from inyoka.conf import settings

import datetime

class TestUserModel(unittest.TestCase):
    def setUp(self):
        self.user = User.objects.register_user('testing', 'example@example.com',
                                               'pwd', False)

    def test_reactivation(self):
        result = reactivate_user(self.user.id, '', '', datetime.datetime.now())
        self.assert_('failed' in result)
        result = reactivate_user(self.user.id, '', '', datetime.datetime.now()-\
                                 datetime.timedelta(days=34))
        self.assert_('failed' in result)
        self.user.status = 3
        self.user.save()
        result = reactivate_user(self.user.id, 'example_new@example.com',\
                                 1, datetime.datetime.now())
        self.assert_('success' in result)
        self.user = User.objects.get(pk=self.user.id)
        self.assertEqual(self.user.status, 1)

    def test_deactivation(self):
        deactivate_user(self.user)
        self.user = User.objects.get(pk=self.user.id)
        self.assertEqual(self.user.status, 3)

    def test_postcount(self):
        self.assertEqual(self.user.post_count, 0)
        self.user.inc_post_count()
        self.user = User.objects.get(pk=self.user.id)
        self.assertEqual(self.user.post_count, 1)

    def tearDown(self):
        self.user.delete()

class TestGroupModel(unittest.TestCase):
    def setUp(self):
        self.group = Group.objects.create(name='testing', is_public=True)

    def test_icon(self):
        self.assertEqual(self.group.icon_url, None)
        # TODO

    def tearDown(self):
        self.group.delete()
