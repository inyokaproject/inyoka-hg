#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.render_posts
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
from sqlalchemy.sql import desc
from inyoka.forum.models import Post
from inyoka.utils.database import session


def render_posts():
    query = Post.query.filter(Post.c.rendered_text != '') \
                      .order_by(desc(Post.c.id)) \
                      .limit(100)
    result = query.all()
    while result:
        for post in result:
            post.rendered_text = post.render_text(nocache=True,
                                                  force_existing=True)
            session.commit()
        result = query.all()
