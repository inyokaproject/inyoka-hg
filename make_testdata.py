#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.make_testadata
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
from __future__ import division
import math
import time
from random import randint, choice
from datetime import datetime
from jinja.constants import LOREM_IPSUM_WORDS
from inyoka.conf import settings
from inyoka.portal.user import User, Group
from inyoka.forum.models import Forum, Topic, Post, Privilege
from inyoka.forum.acl import PRIVILEGES
from inyoka.ikhaya.models import Category, Article, Comment
from inyoka.wiki.models import Page
from inyoka.utils.database import session

MARKS = ('.', ';', '!', '?')
WORDS = LOREM_IPSUM_WORDS.split(' ')
NAME_WORDS = [w for w in WORDS if not '\n' in w]

groups = []
users = []
page_names = []
forums = []


def create_names(count, func=lambda: choice(NAME_WORDS)):
    """Yields a bunch of unique names"""
    used = []
    for _ in xrange(count):
        for _ in xrange(100):
            if _ < 5:
                name = func()
            else:
                # put some random into the names
                name = '%d%s' % (randint(1, 100), func())
            if name not in used:
                yield name
                used.append(name)
                break


def word(markup=True):
    word = choice(WORDS)
    modifiers = [
        lambda t: '[:%s:%s]' % (choice(page_names), t),
        "'''%s'''", "''%s''", '__%s__', '[http://ubuntuusers.de %s]']
    if markup:
        for modifier in modifiers:
            if randint(1, 50) == 1:
                if hasattr(modifier, '__call__'):
                    word = modifier(word)
                else:
                    word = modifier % word
                break
    return word


def words(min=4, max=20, markup=True):
    ws = []
    for i in xrange(randint(min, max)):
        w = word(markup)
        if i == 0:
            w = w.capitalize()
        ws.append(w)
    return '%s%s' % (' '.join(ws), choice(MARKS))


def sentences(min=5, max=35, markup=True):
    s_list = []
    nls = ['\n\n', '\n\n\n\n', '\n', '']
    for i in xrange(randint(min, max)):
        s_list.append(
            words(markup) + choice(nls)
        )
    return ' '.join(s_list)


def title():
    return words(2, 3, markup=False)


def intro(markup=True):
    return sentences(min=3, max=10, markup=markup)


def randtime():
    return datetime.fromtimestamp(randint(0, math.floor(time.time())))


def make_groups():
    print 'Creating groups'
    for name in create_names(10):
        groups.append(Group(name=name, is_public=bool(randint(0, 1))))
        groups[-1].save()


def make_users():
    print 'Creating users'
    for name in create_names(30):
        u = User.objects.register_user(
            name, '%s@ubuntuusers.local' % name, name, False)
        u.date_joined = randtime()
        u.last_login = randtime()
        for _ in xrange(randint(0, 5)):
            u.groups.add(choice(groups))
        u.post_count = randint(0, 1000)
        u.jabber = '%s@%s.local' % (word(markup=False), word(markup=False))
        u.icq = word(markup=False)[:16]
        u.msn = word(markup=False)
        u.aim = word(markup=False)
        u.signature = words()
        u.occupation = word(markup=False)
        u.interests = word(markup=False)
        u.website = u'http://%s.de' % word(markup=False)
        if not randint(0, 3):
            u.is_active = False
        u.save()
        users.append(u)


def make_forum():
    print 'Creating forum test data'
    try:
        admin = User.objects.filter(is_manager=True)[0]
    except:
        admin = None
    for name in create_names(7, title):
        parent = None
        if randint(1, 6) != 6:
            try:
                parent = choice(forums)
            except IndexError:
                pass
        f = Forum(name=name, parent=parent)
        if admin is not None:
            Privilege(user_id=admin.id, forum=f, **dict.fromkeys(['can_' + x for x in PRIVILEGES], True))
        forums.append(f)
        session.commit()
        if parent:
            for _ in xrange(randint(1, 3)):
                author = choice(users)
                t = Topic(title=title()[:100], author_id=author.id, forum=f)
                p = Post(topic=t, text=sentences(min=1, max=10), author_id=author.id, pub_date=randtime())
                session.commit()
                for _ in xrange(randint(1, 40)):
                    p = Post(topic=t, text=sentences(min=1, max=10), author_id=choice(users).id, pub_date=randtime())
            session.commit()
    # all about the wiki - forum (and diskussions subforum)
    f = Forum(name=u'Rund ums Wiki', parent=None)
    d = Forum(name=u'Diskussionen', slug=settings.WIKI_DISCUSSION_FORUM, parent=f)
    forums.append(f)
    forums.append(d)
    session.commit()


def make_ikhaya():
    print 'Creating ikhaya test data'
    for name in create_names(5, title):
        c = Category(name=name)
        c.save()
        for name in create_names(5, title):
            a = Article(
                pub_date=randtime(),
                author_id=choice(users).id,
                subject=name,
                category_id=c.id,
                intro=intro(),
                text=sentences(),
                public=True,
                is_xhtml=False
            )
            a.save()
            for i, name in enumerate(create_names(randint(0, 5), title)):
                text = sentences(min=1, max=5)
                if i > 0 and randint(0, 1) == 0:
                    text = '@%d: %s' % (randint(1, i), text)
                Comment(
                    article_id=a.id,
                    title=name,
                    text=text,
                    author_id=choice(users).id,
                    pub_date=randtime()
                ).save()


def make_wiki():
    print 'Creating wiki pages'
    for name in page_names:
        Page.objects.create(name, sentences(min=10, max=20),
                            choice(users), note=title())


if __name__ == '__main__':
    page_names = ['Startseite'] + list(create_names(20))
    make_groups()
    make_users()
    make_wiki()
    make_ikhaya()
    make_forum()
