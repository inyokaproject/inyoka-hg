#-*- coding: utf-8 -*-
"""
    portal/test_portal_views
    ~~~~~~~~~~~~~~~~~~~~~~~~

    This module tests the portal views
"""
from tests import view_test


@view_test('/', component='portal')
def test_index(client, tctx, ctx):
    #TODO: this is just for demonstration. We need to write some
    #      more useful tests :-)
    assert tctx['pm_count'] == 0
