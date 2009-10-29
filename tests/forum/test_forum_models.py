#-*- coding: utf-8 -*-
"""
    test_forum_models
    ~~~~~~~~~~~~~~~~~


    Test the model API of all classes in `inyoka.forum.models`.

    :copyright: 2008 by Christoph Hack
    :license: GNU GPL.
"""
from py.test import raises
from inyoka.forum.models import Forum, Topic, Post, SAUser
from inyoka.utils.database import session

'''
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


def test_topic_in_category():
    """
    Try to create a new topic inside a category.
    """
    global initial
    session.remove()
    category = Forum.query.get(initial['category'].id)
    user = SAUser.query.get(initial['user'].id)
    topic = Topic(forum=category, title=u'py.test Topic', author=user)
    raises(ValueError, session.commit)


def test_integrity():
    """
    Check the forum structure and the post/topic counts as well as foreign keys.
    """
    global initial
    session.remove()
    c = Forum.query.get(initial['category'].id)
    f1 = Forum.query.get(initial['forum1'].id)
    f2 = Forum.query.get(initial['forum2'].id)
    t = Topic.query.get(initial['topic'].id)
    posts = Post.query.filter_by(topic_id=t.id).all()
    user =  SAUser.query.get(initial['user'].id)

    assert set([x.id for x in c.children]) == set([
        initial['forum1'].id, initial['forum2'].id])
    assert [x.id for x in f1.parents] == [initial['category'].id]
    assert len(posts) == 2

    assert t.last_post_id == posts[-1].id
    assert t.first_post_id == posts[0].id
    assert f1.last_post_id == posts[-1].id
    assert c.last_post_id == posts[-1].id
    assert f2.last_post_id == None
    assert user.post_count == initial['user'].post_count + 2
    assert c.topic_count == 1
    assert c.post_count == 2
    assert f1.topic_count == 1
    assert f1.post_count == 2
    assert f2.topic_count == 0
    assert f2.post_count == 0


def test_duplicate_slug():
    global initial
    session.remove()
    forum = Forum.query.get(initial['forum1'].id)
    user = SAUser.query.get(initial['user'].id)
    t = Topic(forum=forum, title=initial['topic'].title, author=user)
    session.commit()
    session.delete(t)
    session.commit()
'''
