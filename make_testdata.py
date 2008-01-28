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
from django.conf import settings
from inyoka.portal.user import User, Group

MARKS = ('.', ';', '!', '?')
WORDS = LOREM_IPSUM_WORDS.split(' ')
WORDS = ['<script>alert("XSS")</script>', '"><script>alert("XSS")</script><"',
         "'><script>alert('XSS')</script><'", '">', "'>"]

def word():
    return choice(WORDS)


def words(min=4, max=20):
    ws = []
    for i in xrange(randint(min, max)):
        w = word()
        if i == 0:
            w = w.capitalize()
        ws.append(w)
    return '%s%s' % (' '.join(ws), choice(MARKS))


def sentences(min=5, max=100):
    s_list = []
    nls = ['\n\n', '\n\n\n\n', '\n', '']
    for i in xrange(randint(min, max)):
        s_list.append(
            words() + choice(nls)
        )
    return ' '.join(s_list)


def title():
    return words(2, 3)


def intro():
    return sentences(min=3, max=10)

def text():
    return sentences()

def randtime():
    return datetime.fromtimestamp(randint(0, math.floor(time.time())))


def make_groups():
    print 'Creating groups'
    groups = []
    for _ in xrange(10):
        groups.append(Group(name=word() + str(randint(1, 999999)), is_public=bool(randint(0, 1))))
        groups[-1].save()
    return groups

def make_users(groups):
    print 'Creating users'
    names = []
    for _ in xrange(30):
        while True:
            name = (str(randint(0, 99999)) + word())[:30]
            if name not in names:
                names.append(name)
                break
        u = User.objects.register_user(
            name, '%s@ubuntuusers.local' % name, name, False)
        u.date_joined = randtime()
        u.last_login = randtime()
        for _ in xrange(randint(0, 5)):
            u.groups.add(choice(groups))
        u.post_count = randint(0, 1000)
        u.jabber = '%s@%s.%s' % (word(), word(), word())
        u.icq = word()[:16]
        u.msn = word()
        u.aim = word()
        u.signature = words()
        u.occupation = word()
        u.interests = word()
        u.website = u'http://xyz%s.de' % word()
        if not randint(0, 3):
            u.is_active = False
        u.save()
        yield u



def make_forum(users):
    print 'Creating forum test data'
    forums = []
    admin = User.objects.get(username="admin")
    from inyoka.forum.models import Forum, Topic, Privilege
    from inyoka.forum.acl import PRIVILEGES
    for _ in xrange(7):
        parent = None
        if randint(1, 6) != 6:
            try:
                parent = choice(forums)
            except IndexError:
                pass
        f = Forum(name=title() + str(randint(1, 9999)), parent=parent)
        f.save()
        Privilege(user=admin, forum=f, **dict.fromkeys(['can_' + x for x in PRIVILEGES], True)).save()
        forums.append(f)
        if parent != None:
            for _ in xrange(randint(1, 3)):
                t = Topic.objects.create(f, title()[:100], text(), author=
                                         choice(users), pub_date=randtime())
                for _ in xrange(randint(1, 10)):
                    t.reply(sentences(min=1, max=10), choice(users), randtime())
    # all about the wiki - forum (and diskussions subforum)
    f = Forum(name=u'Rund ums Wiki', parent=None)
    f.save()
    d = Forum(name=u'Diskussionen', slug=settings.WIKI_DISCUSSION_FORUM, parent=f)
    d.save()


def make_ikhaya(users):
    print 'Creating ikhaya test data'
    from inyoka.ikhaya.models import Category, Article
    for _ in xrange(5):
        c = Category(name='%s%s' % (randint(1, 9999), title()))
        c.save()
        for _ in xrange(5):
            a = Article(
                pub_date=randtime(),
                author=choice(users),
                subject=title(),
                category=c,
                intro=intro(),
                text=text(),
                public=True,
                is_xhtml=True
            )
            a.save()


users = list(make_users(make_groups()))
make_forum(users)
make_ikhaya(users)
