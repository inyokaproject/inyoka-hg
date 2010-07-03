# -*- coding: utf-8 -*-
"""
    inyoka.forum.models
    ~~~~~~~~~~~~~~~~~~~

    Database models for the forum.

    :copyright: 2007-2010 by Florian Apolloner.
    :license: GNU GPL, see LICENSE for more details.
"""
from django.db import models

from inyoka.portal.user import User, Group


class Welcomemessage(models.Model):
    title = models.CharField(max_length=120)
    text = models.TextField()
    rendered_text = models.TextField()


class Forum(models.Model):
    name = models.CharField(max_length=100)
    slug = models.CharField(unique=True, max_length=100)
    description = models.TextField()
    parent = models.ForeignKey('self', null=True, blank=True)
    position = models.IntegerField()
    last_post = models.ForeignKey('Post', null=True, blank=True)
    post_count = models.IntegerField()
    topic_count = models.IntegerField()
    welcome_message = models.ForeignKey(Welcomemessage, null=True, blank=True)
    newtopic_default_text = models.TextField(blank=True, null=True)
    user_count_posts = models.BooleanField()
    force_version = models.BooleanField()


class Topic(models.Model):
    forum = models.ForeignKey(Forum)
    title = models.CharField(max_length=100)
    slug = models.CharField(unique=True, max_length=50)
    view_count = models.IntegerField()
    post_count = models.IntegerField()
    sticky = models.BooleanField()
    solved = models.BooleanField()
    locked = models.BooleanField()
    reported = models.TextField(blank=True, null=True)
    reporter = models.ForeignKey(User, related_name='reported_topics',
                                 null=True, blank=True)
    hidden = models.BooleanField()
    ubuntu_version = models.CharField(max_length=5, blank=True)
    ubuntu_distro = models.CharField(max_length=40, blank=True)
    author = models.ForeignKey(User, related_name='created_topics')
    first_post = models.ForeignKey('Post', related_name='topic_set',
                                   null=True, blank=True)
    last_post = models.ForeignKey('Post', related_name='topic_set2',
                                  null=True, blank=True)
    has_poll = models.BooleanField()
    report_claimed_by = models.ForeignKey(User, related_name='claimed_topics',
                                          null=True, blank=True)


class Post(models.Model):
    position = models.IntegerField()
    author = models.ForeignKey(User)
    pub_date = models.DateTimeField()
    topic = models.ForeignKey(Topic)
    hidden = models.BooleanField()
    text = models.TextField(blank=True)
    rendered_text = models.TextField(blank=True)
    has_revision = models.BooleanField()
    is_plaintext = models.BooleanField()


class Attachment(models.Model):
    file = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    comment = models.TextField()
    post = models.ForeignKey(Post, null=True, blank=True)
    mimetype = models.CharField(max_length=100, blank=True)


class Poll(models.Model):
    question = models.CharField(max_length=250)
    topic = models.ForeignKey(Topic, null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    multiple_votes = models.BooleanField()


class Polloption(models.Model):
    poll = models.ForeignKey(Poll)
    name = models.CharField(max_length=250)
    votes = models.IntegerField()


class Postrevision(models.Model):
    post = models.ForeignKey(Post)
    text = models.TextField()
    store_date = models.DateTimeField()


class Privilege(models.Model):
    group = models.ForeignKey(Group, null=True, blank=True)
    user = models.ForeignKey(User, null=True, blank=True)
    forum = models.ForeignKey(Forum)
    positive = models.IntegerField(null=True, blank=True)
    negative = models.IntegerField(null=True, blank=True)


class Voter(models.Model):
    voter = models.ForeignKey(User)
    poll = models.ForeignKey(Poll)
