#-*- coding: utf-8 -*-
"""
    test_forum_models
    ~~~~~~~~~~~~~~~~~

    This module tests all models and views in `inyoka.forum.models`.

    :copyright: 2008-2009 by Christoph Hack, Christopher Grebs.
    :license: GNU GPL.
"""
from inyoka.conf import settings
from inyoka.forum.models import Forum, Topic, Post
from inyoka.forum.compat import SAUser
from inyoka.utils.database import session

# This is the global context that will be created
# for all `forum` related tests.
tctx = {}

'''
def setup_package(pkg):
    """Setup the database, create some test data for the forum unittests"""
    c = Forum(parent=None, name='

def setup_module(module):
    """
    Create some test data for playing arround.
    """
    c   = Forum(parent=None, name='py.test Category')
    f1  = Forum(parent=c, name='py.test Forum 1', position=2)
    f2  = Forum(parent=c, name='py.test Forum 2', position=1)
    u   = SAUser.query.first()
    t   = Topic(forum=f1, title=u'py.test Topic', author=u)
    p1  = Post(topic=t, text=u'Hello World.', author=u)
    session.commit()
    session.remove()

    t   = Topic.query.get(t.id)
    p2  = Post(topic=t, text=u'Another Post', author=u)
    session.commit()

    module.initial = {
        'category': c,
        'forum1':   f1,
        'forum2':   f2,
        'user':     u,
        'topic':    t,
        'post1':    p1,
        'post2':    p2
    }


def teardown_module(module):
    """
    Remove the test data again.
    """
    global initial
    session.remove()
    forums = [
        Forum.query.get(initial['category'].id),
        Forum.query.get(initial['forum1'].id),
        Forum.query.get(initial['forum2'].id)
    ]
    for forum in reversed([f for f in forums if f]):
        session.delete(forum)
    topic = Topic.query.get(initial['topic'].id)
    if topic:
        session.delete(topic)
    session.commit()
'''
