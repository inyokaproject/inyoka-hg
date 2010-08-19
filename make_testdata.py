#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.make_testadata
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
from __future__ import division
import sys
import math
import time
from random import randint, choice
from datetime import datetime
from itertools import cycle, izip
from jinja2.constants import LOREM_IPSUM_WORDS
from inyoka.conf import settings
settings.DEBUG = settings.DATABASE_DEBUG = False # for nice progressbar output ;)

# circular imports rocks!
import inyoka.application

from inyoka.portal.user import User, Group
from inyoka.forum.models import Forum, Topic, Post, Privilege
from inyoka.forum.acl import join_flags, PRIVILEGES
from inyoka.ikhaya.models import Category, Article, Comment
from inyoka.wiki.models import Page
from inyoka.utils.database import session
from inyoka.utils.captcha import generate_word
from inyoka.utils.text import increment_string


MARKS = ('.', ';', '!', '?')
WORDS = LOREM_IPSUM_WORDS.split(' ')
NAME_WORDS = [w for w in WORDS if not '\n' in w]

groups = []
users = []
page_names = []
forums = []

GROUPS_COUNT = 30
USERS_COUNT = 300
FORUMS_COUNT = 20
MAX_TOPIC_COUNT = 20
MAX_TOPIC_POST_COUNT = 28
IKHAYA_ARTICLE_COUNT = 30
WIKI_PAGES_COUNT = 200


# original from Jochen Kupperschmidt with some modifications
class ProgressBar(object):
    """Visualize a status bar on the console."""

    def __init__(self, max_width):
        """Prepare the visualization."""
        self.max_width = max_width
        self.spin = cycle(r'-\|/').next
        self.tpl = '%-' + str(max_width) + 's ] %c %5.1f%%'
        show(' [ ')
        self.last_output_length = 0

    def update(self, percent):
        """Update the visualization."""
        # Remove last state.
        show('\b' * self.last_output_length)

        # Generate new state.
        width = int(percent / 100.0 * self.max_width)
        output = self.tpl % ('-' * width, self.spin(), percent)

        # Show the new state and store its length.
        show(output)
        self.last_output_length = len(output)


def show(string):
    """Show a string instantly on STDOUT."""
    sys.stdout.write(string)
    sys.stdout.flush()


def percentize(steps):
    """Generate percental values."""
    for i in range(steps + 1):
        yield i * 100.0 / steps


def create_names(count, func=lambda: choice(NAME_WORDS)):
    """Yields a bunch of unique names"""
    used = []
    for _ in xrange(count+1):
        name = func()
        if name in used:
            # use some random...
            name = '%s%s%d' % (generate_word(), name, randint(1, 100))
        if name in used:
            # now we need to increment that thingy...
            name = increment_string(name)
        used.append(name)
        yield name


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
        s_list.append(words(markup) + choice(nls))
    return ' '.join(s_list)


def title():
    return u''.join(w for w in words(2, 3, markup=False) if not '\n' in w)


def intro(markup=True):
    return sentences(min=3, max=10, markup=markup)


def randtime():
    return datetime.fromtimestamp(randint(0, math.floor(time.time())))


def make_groups():
    print 'Creating groups'
    pb = ProgressBar(40)
    for percent, name in izip(percentize(GROUPS_COUNT), create_names(GROUPS_COUNT)):
        groups.append(Group(name=name))
        groups[-1].save()
        pb.update(percent)
    show('\n')


def make_users():
    print 'Creating users'
    pb = ProgressBar(40)
    for percent, name in izip(percentize(USERS_COUNT), create_names(USERS_COUNT)):
        u = User.objects.register_user(
            name, '%s@ubuntuusers.local' % name, name, False)
        u.date_joined = randtime()
        u.last_login = randtime()
        u.groups = list(set(choice(groups) for _ in xrange(randint(0, 5))))
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
            u.status = 0
        u.save()
        users.append(u)
        pb.update(percent)
    show('\n')


def make_forum():
    print 'Creating forum test data'
    pb = ProgressBar(40)
    for percent, name in izip(percentize(FORUMS_COUNT), create_names(FORUMS_COUNT, title)):
        parent = None
        if randint(1, 6) != 6:
            try:
                parent = choice(forums)
            except IndexError:
                pass
        f = Forum(name=name, parent=parent)
        session.flush()
        forums.append(f)
        session.commit()
        if parent:
            for _ in xrange(randint(1, MAX_TOPIC_COUNT)):
                author = choice(users)
                t = Topic(title=title()[:100], author_id=author.id, forum=f)
                p = Post(topic=t, text=sentences(min=1, max=10),
                    author_id=author.id, pub_date=randtime(), position=0)
                session.commit()
                for i in xrange(randint(1, MAX_TOPIC_POST_COUNT)):
                    p = Post(topic=t, text=sentences(min=1, max=10),
                        author_id=choice(users).id, pub_date=randtime(),
                        position=i + 1)
            session.commit()
        pb.update(percent)
    # all about the wiki - forum (and diskussions subforum)
    f = Forum(name=u'Rund ums Wiki', parent=None)
    d = Forum(name=u'Diskussionen', slug=settings.WIKI_DISCUSSION_FORUM, parent=f)
    session.flush()
    forums.append(f)
    forums.append(d)
    session.commit()
    show('\n')


def make_ikhaya():
    print 'Creating ikhaya test data'
    pb = ProgressBar(40)
    for percent, name in izip(percentize(IKHAYA_ARTICLE_COUNT), create_names(IKHAYA_ARTICLE_COUNT, title)):
        c = Category(name=name)
        c.save()
        for name in create_names(30, title):
            dt = randtime()
            a = Article(
                pub_date=dt.date(),
                pub_time=dt.time(),
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
                    text=text,
                    author_id=choice(users).id,
                    pub_date=randtime()
                ).save()
        pb.update(percent)
    show('\n')


def make_wiki():
    print 'Creating wiki pages'
    pb = ProgressBar(40)
    for percent, name in izip(percentize(len(page_names)), page_names):
        Page.objects.create(name, sentences(min=10, max=20),
                            choice(users), note=title())
        pb.update(percent)
    show('\n')


if __name__ == '__main__':
    page_names = ['Startseite'] + list(create_names(WIKI_PAGES_COUNT))
    make_groups()
    make_users()
    make_wiki()
    make_ikhaya()
    make_forum()
    print "created test data"
