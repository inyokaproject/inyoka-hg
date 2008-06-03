# -*- coding: utf-8 -*-
"""
    inyoka.forum.views
    ~~~~~~~~~~~~~~~~~~

    The views for the forum.

    :copyright: Copyright 2007 by Benjamin Wiegand, Christopher Grebs,
                                  Christoph Hack.
    :license: GNU GPL.
"""
import re
from django.conf import settings
from datetime import datetime, timedelta
from django.utils.text import truncate_html_words
from sqlalchemy.orm import eagerload
from sqlalchemy.sql import and_, select
from sqlalchemy.exceptions import InvalidRequestError
from inyoka.utils.urls import global_not_found
from inyoka.portal.utils import simple_check_login, abort_access_denied
from inyoka.portal.user import User
from inyoka.utils.urls import href, url_for
from inyoka.utils.html import escape
from inyoka.utils.sessions import set_session_info
from inyoka.utils.http import templated, does_not_exist_is_404, \
    PageNotFound, HttpResponseRedirect
from inyoka.utils.feeds import FeedBuilder
from inyoka.utils.flashing import flash
from inyoka.utils.templating import render_template
from inyoka.utils.pagination import Pagination
from inyoka.utils.notification import send_notification
from inyoka.utils.cache import cache
from inyoka.utils.dates import format_datetime
from inyoka.utils.database import session
from inyoka.utils.storage import storage
from inyoka.wiki.utils import quote_text, normalize_pagename
from inyoka.wiki.parser import parse, RenderContext
from inyoka.wiki.models import Page
from inyoka.portal.models import Subscription
from inyoka.forum.models import Forum, Topic, POSTS_PER_PAGE, Post, Poll, \
    TOPICS_PER_PAGE, PollVote, PollOption, Attachment, PostRevision
from inyoka.forum.forms import NewTopicForm, SplitTopicForm, EditPostForm, \
    AddPollForm, MoveTopicForm, ReportTopicForm, ReportListForm, \
    AddAttachmentForm
from inyoka.forum.acl import filter_invisible, get_forum_privileges, \
    have_privilege, get_privileges, CAN_READ, CAN_MODERATE, \
    check_privilege
from inyoka.forum.database import post_table, topic_table, forum_table, \
    poll_option_table, attachment_table

_legacy_forum_re = re.compile(r'^/forum/(\d+)(?:/(\d+))?/?$')


def not_found(request, err_message=None):
    """
    This is called if no URL matches or a view returned a `PageNotFound`.
    """
    from inyoka.forum.legacyurls import test_legacy_url
    response = test_legacy_url(request)
    if response is not None:
        return response
    return global_not_found(request, 'forum', err_message)


@templated('forum/index.html')
def index(request, category=None):
    """
    Return all forums without parents.
    These forums are treated as categories but not as real forums.
    """
    categories = []
    if category:
        category = Forum.query.get(category)
        if not category or category.parent_id != None:
            raise PageNotFound
        fmsg = category.find_welcome(request.user)
        if fmsg is not None:
            return welcome(request, fmsg.slug, request.path)
        set_session_info(request, (u'sieht sich die Forenübersicht der '
                                   u'Kategorie „%s“ an'
                                   % category.name),
                         u'Kategorieübersicht')
        categories = [category]
    else:
        categories = Forum.query.filter(forum_table.c.parent_id == None)
        set_session_info(request, u'sieht sich die Forenübersicht an.',
                         u'Forenübersicht')

    hidden_categories = []
    if request.user.is_authenticated:
        hidden_categories.extend(request.user.settings.get(
            'hidden_forum_categories', ())
        )

    return {
        'categories':           filter_invisible(request.user, categories),
        'is_index':             not category,
        'hidden_categories':    hidden_categories
    }


@templated('forum/forum.html')
def forum(request, slug, page=1):
    """
    Return a single forum to show a topic list.
    """
    f = Forum.query.get(slug)
    # if the forum is a category we raise PageNotFound.  categories have
    # their own url at /category.
    if not f or f.parent_id is None:
        raise PageNotFound()
    privs = get_forum_privileges(request.user, f.id)
    if not check_privilege(privs, 'read'):
        return abort_access_denied(request)
    fmsg = f.find_welcome(request.user)
    if fmsg is not None:
        return welcome(request, fmsg.slug, request.path)
    page = int(page)

    key = 'forum/topics/%d/%d' % (f.id, int(page))
    data = cache.get(key)
    if not data:
        topics = Topic.query.options(eagerload('author'), eagerload('last_post'),
            eagerload('last_post.author')).filter_by(forum_id=f.id) \
            .order_by((topic_table.c.sticky.desc(), topic_table.c.last_post_id.desc()))
        pagination = Pagination(request, topics, page, TOPICS_PER_PAGE, url_for(f),
                                total=f.topic_count)
        data = {
            'forum':            f,
            'topics':           list(pagination.objects),
            'pagination_left':  pagination.generate(),
            'pagination_right': pagination.generate('right')
        }
        # if you alter this value, change it in
        # forum.models.Forum.invalidate_topic_cache, too.
        if page < 5:
            cache.set(key, data)

    key = 'forum/subforums/%d' % f.id
    subforums = cache.get(key)
    if not subforums:
        subforums = Forum.query.options(eagerload('last_post'),
            eagerload('last_post.author')).filter_by(parent_id=f.id).all()
        cache.set(key, subforums)

    set_session_info(request, u'sieht sich das Forum „<a href="%s">'
                     u'%s</a>“ an' % (escape(url_for(f)), escape(f.name)),
                     'besuche das Forum')
    data.update({
        'subforums':     filter_invisible(request.user, subforums),
        'is_subscribed': Subscription.objects.user_subscribed(request.user,
                                                                 forum=f),
        'can_moderate' = check_privilege(privs, 'moderate'),
    })
    return data


@templated('forum/topic.html')
def viewtopic(request, topic_slug, page=1):
    """
    Shows a topic, the posts are paginated.
    If the topic has a `hidden` flag, the user gets a nice message that the
    topic is deleted and is redirected to the topic's forum.  Moderators can
    see these topics.
    """
    t = Topic.query.filter_by(slug=topic_slug).first()
    if not t:
        raise PageNotFound('no such topic')
    privileges = get_forum_privileges(request.user, t.forum.id)
    if not check_privilege(privileges, 'read'):
        return abort_access_denied(request)
    if t.hidden:
        if not check_privilege(privileges, 'moderate'):
            # XXX: don't show the topic if the user isn't a moderator
            flash(u'Dieses Thema wurde von einem Moderator gelöscht.')
            return HttpResponseRedirect(url_for(t.forum))
        flash(u'Dieses Thema ist unsichtbar für normale Benutzer.')
    fmsg = t.forum.find_welcome(request.user)
    if fmsg is not None:
        return welcome(request, fmsg.slug, request.path)
    t.touch()
    session.commit()

    posts = t.posts

    if t.has_poll:
        polls = Poll.query.options(eagerload('options')).filter(
            Poll.topic_id==t.id).all()

        if request.method == 'POST' and request.user.is_authenticated:
            # the user participated in a poll
            for poll in polls:
                # get the votes for every poll in this topic
                if poll.multiple_votes:
                    votes = request.POST.getlist('poll_%s' % poll.id)
                else:
                    votes = [request.POST.get('poll_%s' % poll.id)]
                if votes:
                    if not check_privilege(privileges, 'vote'):
                        return abort_access_denied(request)
                    elif poll.participated:
                        flash(u'Du hast bereits an dieser Abstimmung '
                              u'teilgenommen.', False)
                        continue
                    elif poll.ended:
                        flash(u'Die Abstimmung ist bereits zu Ende.', False)
                        continue
                    poll.votings.append(PollVote(voter_id=request.user.id))
                    session.execute(poll_option_table.update(
                        poll_option_table.c.id.in_(votes) &
                        (poll_option_table.c.poll_id == poll.id), values={
                            'votes': poll_option_table.c.votes + 1
                    }))
                    flash(u'Deine Stimme wurde gespeichert.', True)
            session.commit()
            for poll in polls:
                for option in poll.options:
                    session.refresh(option)
    else:
        polls = None

    pagination = Pagination(request, posts, page, POSTS_PER_PAGE, url_for(t),
                            total=t.post_count)
    set_session_info(request, u'sieht sich das Thema „<a href="%s">%s'
        u'</a>“ an' % (url_for(t), escape(t.title)), 'besuche Thema')
    subscribed = False
    if request.user.is_authenticated:
        t.mark_read(request.user)
        request.user.save()

        try:
            s = Subscription.objects.get(user=request.user,
                                     topic_id=t.id)
            subscribed = True
            s.notified = False
            s.save()
        except Subscription.DoesNotExist:
            subscribed = False

    post_objects = pagination.objects.options(eagerload('attachments'),
                                              eagerload('author')).all()

    for post in post_objects:
        if not post.rendered_text:
            post.rendered_text = post.render_text(force_existing=True)
            session.commit()
    team_icon = storage['team_icon']

    if team_icon:
        team_icon = href('media', storage['team_icon'])
    else:
        team_icon = None

    can_mod = check_privilege(privileges, 'moderate')
    can_reply = check_privilege(privileges, 'reply')


    return {
        'topic':             t,
        'forum':             t.forum,
        'posts':             post_objects,
        'is_subscribed':     subscribed,
        'pagination':        pagination,
        'polls':             polls,
        'show_vote_results': request.GET.get('action') == 'vote_results',
        'can_vote':          polls and bool([True for p in polls if p.can_vote]),
        'can_moderate':      can_mod,
        'can_edit':          lambda post: can_mod or (post.author_id ==
                                          request.user.id and can_reply),
        'can_reply':         can_reply,
        'team_icon_url':     team_icon
    }


@templated('forum/edit.html')
def edit(request, forum_slug=None, topic_slug=None, post_id=None,
         quote_id=None, article_name=None):
    """
    This function allows the user to create a new topic which is created in
    the forum `slug` if `slug` is a string.
    Else a new discussion for the wiki article `article` is created inside a
    special forum that contains wiki discussions only (see the
    WIKI_DISCUSSION_FORUM setting).  It's title is set to the wiki article's
    name.
    When creating a new topic, the user has the choice to upload files bound
    to this topic or to create one or more polls.
    """
    post = topic = forum = attachment = quote = posts = None
    newtopic = False
    poll_form = poll_options = polls = None
    attach_form = None
    attachments = []
    preview = None
    article = None
    if article_name:
        article = Page.objects.get(name=normalize_pagename(article_name))
        forum_slug = settings.WIKI_DISCUSSION_FORUM
        flash(u'Zu dem Artikel „%s“ existiert noch keine Diskussion. '
              u'Wenn du willst, kannst du hier eine neue anlegen.' %
                                                (escape(article_name)))
    if topic_slug:
        try:
            topic = Topic.query.filter_by(slug=topic_slug).one()
        except InvalidRequestError:
            raise PageNotFound()
        if not topic:
            raise PageNotFound()
        forum = topic.forum
    elif forum_slug:
        forum = Forum.query.get(forum_slug)
        if not forum or not forum.parent_id:
            raise PageNotFound()
        newtopic = True
    elif post_id:
        post = Post.query.get(post_id)
        if not post:
            raise PageNotFound()
        topic = post.topic
        forum = topic.forum
        newtopic = post.id == topic.first_post_id
    elif quote_id:
        quote = Post.query.options(eagerload('topic'), eagerload('author')) \
                          .get(quote_id)
        if not quote:
            raise PageNotFound()
        topic = quote.topic
        forum = topic.forum
    if newtopic:
        form = NewTopicForm(request.POST or None, initial={
            'text': forum.newtopic_default_text})
    else:
        form = EditPostForm(request.POST or None)

    # check privileges
    privileges = get_forum_privileges(request.user, forum.id)
    if post:
        if not (check_privilege(privileges, 'moderate') or
                (post.author_id == request.user.id and
                 check_privilege(privileges, 'reply'))):
            return abort_access_denied(request)
    elif topic:
        if not check_privilege(privileges, 'reply'):
            return abort_access_denied(request)
    else:
        if not check_privilege(privileges, 'create'):
            return abort_access_denied(request)

    # the user has canceled the action
    if request.method == 'POST' and request.POST.get('cancel'):
        flash(u'Der Bearbeitungsvorgang wurde abgebrochen')
        url = href('forum')
        if forum_slug:
            url = href('forum', 'forum', forum.slug)
        elif topic_slug:
            url = href('forum', 'topic', topic.slug)
        elif post_id:
            url = href('forum', 'post', post.id)
        return HttpResponseRedirect(url)

    #  handle polls
    poll_ids = map(int, filter(bool, request.POST.get('polls', '').split(',')))
    if newtopic and check_privilege(privileges, 'create_poll'):
        poll_form = AddPollForm(('add_poll' in request.POST or
            'add_option' in request.POST) and request.POST or None)
        poll_options = request.POST.getlist('options') or ['', '']

        if 'add_poll' in request.POST and poll_form.is_valid():
            d = poll_form.cleaned_data
            options = map(lambda a: PollOption(name=a), poll_options)
            now = datetime.utcnow()
            end_time = (d['duration'] and now + timedelta(days=d['duration'])
                        or None)
            poll = Poll(topic=topic, question=d['question'],
                multiple_votes=d['multiple'], options=options,
                start_time=now, end_time=end_time)
            if topic:
                topic.has_poll = True
                topic.forum.invalidate_topic_cache()
            poll_form = AddPollForm()
            poll_options = ['', '']
            flash(u'Die Umfrage "%s" wurde hinzugefügt' % poll.question)
            session.commit()
            poll_ids.append(poll.id)
        elif 'add_option' in request.POST:
            poll_options.append('')

        elif 'delete_poll' in request.POST:
            poll = Poll.query.filter_by(id=request.POST['delete_poll'],
                topic=topic).first()
            if poll:
                flash(u'Die Umfrage "%s" wurde gelöscht' % poll.question)
                topic.has_poll = bool(session.execute(select([1],
                    (Poll.topic_id == topic.id) & (Poll.id != poll.id)) \
                    .limit(1)).fetchone())
                session.delete(poll)
                session.commit()
                topic.forum.invalidate_topic_cache()
        polls = Poll.query.filter(Poll.id.in_(poll_ids) | (Poll.topic_id ==
            (topic and topic.id or -1))).all()

    # handle attachments
    att_ids = map(int, filter(bool,
        request.POST.get('attachments', '').split(',')
    ))
    if check_privilege(privileges, 'upload'):
        # check for post = None to be sure that the user can't "hijack"
        # other attachments.
        attachments = Attachment.query.filter(and_(
            attachment_table.c.id.in_(att_ids),
            attachment_table.c.post_id == bool(post)==True and post.id or None
        )).all()
        if 'attach' in request.POST:
            attach_form = AddAttachmentForm(request.POST, request.FILES)
        else:
            attach_form = AddAttachmentForm()

        if 'attach' in request.POST:
            # the user uploaded a new attachment
            if attach_form.is_valid():
                d = attach_form.cleaned_data
                att_name = d.get('filename') or d['attachment'].filename
                attachment = Attachment.create(
                    att_name, d['attachment'].content,
                    request.FILES['attachment']['content-type'],
                    attachments, override=d['override']
                )
                if not attachment:
                    flash(u'Ein Anhang „%s“ existiert bereits' % att_name, False)
                else:
                    attachment.comment = d['comment']
                    session.commit()
                    attachments.append(attachment)
                    att_ids.append(attachment.id)
                    flash(u'Der Anhang „%s“ wurde erfolgreich hinzugefügt'
                          % att_name, True)

        elif 'delete_attachment' in request.POST:
            id = int(request.POST['delete_attachment'])
            attachment = filter(lambda a: a.id==id, attachments)[0]
            attachment.delete()
            attachments.remove(attachment)
            att_ids.remove(attachment.id)
            session.commit()
            flash(u'Der Anhang „%s“ wurde gelöscht.' % attachment.name)

    # the user submited a valid form
    if 'send' in request.POST and form.is_valid():
        d = form.cleaned_data
        if not topic:
            topic = Topic(forum_id=forum.id, author_id=request.user.id)
        if newtopic:
            topic.title = d['title']
            topic.ubuntu_distro = d['ubuntu_distro']
            topic.ubuntu_version = d['ubuntu_version']
            topic.sticky = d['sticky']
            if check_privilege(privileges, 'create_poll'):
                topic.polls = polls
                topic.has_poll = bool(polls)
            session.flush([topic])

            topic.forum.invalidate_topic_cache()

        if not post:
            post = Post(topic=topic, author_id=request.user.id)
        post.edit(request, d['text'])

        session.flush([post])
        if attachments:
            Attachment.update_post_ids(att_ids, post.id)
        session.commit()

        if forum:
            for s in Subscription.objects.filter(forum_id=forum.id,
                                                 notified=False) \
                                         .exclude(user=request.user):
                send_notification(s.user, 'new_topic', u'Neues Thema im Forum %s: „%s“' %
                                          (forum.name, topic.title), {
                                              'username':   s.user.username,
                                              'post':       post,
                                              'topic':      topic,
                                              'forum':      forum,
                                          })
                # we always notify about new topics, even if the forum was
                # not visited, because unlike the posts you won't see
                # other new topics
        if topic:
            for s in Subscription.objects.filter(topic_id=topic.id,
                                                 notified=False) \
                                         .exclude(user=request.user):
                send_notification(s.user, 'new_post', u'Neue Antwort im Thema „%s“' %
                                          topic.title, {
                                              'username':   s.user.username,
                                              'post':       post,
                                              'topic':      topic,
                                          })
                s.notified = True
                s.save()

        if article:
            # the topic is a wiki discussion, bind it to the wiki
            # article and send notifications.
            article.topic_id = topic.id
            article.save()
            for s in Subscription.objects.filter(wiki_page=article):
                # also notify if the user has not yet visited the page,
                # since otherwise he would never know about the topic
                send_notification(s.user, 'new_page_discussion', u'Neue Diskussion für die '
                    u'Seite „%s“ wurde eröffnet' % article.title, {
                        'username': s.user.username,
                        'page':     article,
                    })
                s.notified = True
                s.save()

        if request.user.settings.get('autosubscribe') and \
           not Subscription.objects.user_subscribed(request.user,
                                                    topic=topic):
            subscription = Subscription(
                user=request.user,
                topic_id=topic.id,
            )
            subscription.save()

        flash(u'Der Beitrag wurde erfolgreich gespeichert')
        return HttpResponseRedirect(url_for(post))

    # the user wants to see a preview
    elif 'preview' in request.POST:
        ctx = RenderContext(request)
        preview = parse(request.POST.get('text', '')).render(ctx, 'html')

    # the user is going to edit an existing post/topic
    elif post:
        form = form.__class__({
            'title': topic.title,
            'ubuntu_distro': topic.ubuntu_distro,
            'ubuntu_version': topic.ubuntu_version,
            'sticky': topic.sticky,
            'text': post.text,
        })
        if not attachments:
            attachments = Attachment.query.filter_by(post_id=post.id)

    # the user is going to quote an existing post
    elif quote:
        form = form.__class__(initial={'text': quote_text(quote.text,
                                                         quote.author)})

    elif newtopic:
        form = form.__class__(initial={
            'title': article and article.name or '',
            'text': forum.newtopic_default_text,
        })

    if not newtopic:
        posts = list(topic.posts.order_by(post_table.c.id.desc())[:15])

    return {
        'form':         form,
        'poll_form':    poll_form,
        'options':      poll_options,
        'polls':        polls,
        'post':         post,
        'forum':        forum,
        'topic':        topic,
        'preview':      preview,
        'isnewtopic':   newtopic,
        'can_attach':   check_privilege(privileges, 'upload'),
        'can_create_poll':     check_privilege(privileges, 'create_poll'),
        'attach_form':  attach_form,
        'attachments':  list(attachments),
        'posts':        posts,
    }


def change_status(request, topic_slug, solved=None, locked=None):
    """Change the status of a topic and redirect to it"""
    t = Topic.query.filter_by(slug=topic_slug).first()
    if not t:
        raise PageNotFound
    if not have_privilege(request.user, t.forum, CAN_READ):
        abort_access_denied(request)
    if solved is not None:
        t.solved = solved
        flash(u'Das Thema wurde als %s markiert' % (solved and u'gelöst' or \
                                                                u'ungelöst'))
    if locked is not None:
        t.locked = locked
        flash(u'Das Thema wurde %s' % (locked and u'gesperrt' or
                                                    u'entsperrt'))
    t.forum.invalidate_topic_cache()

    session.commit()
    return HttpResponseRedirect(t.get_absolute_url())


def _generate_subscriber(obj, obj_slug, subscriptionkw, flasher):
    """
    Generates a subscriber-function to deal with objects of type `obj`
    which have the slug `slug` and are registered in the subscribtion by
    `subscriptionkw` and have the flashing-test `flasher`
    """
    if subscriptionkw in ('forum', 'topic'):
        subscriptionkw = subscriptionkw + '_id'
    subscriptionkw = subscriptionkw
    @simple_check_login
    def subscriber(request, **kwargs):
        """
        If the user has already subscribed to this %s, it just redirects.
        If there isn't such a subscription, a new one is created.
        """ % obj_slug
        slug = kwargs[obj_slug]
        x = obj.query.filter(obj.slug==slug).one()
        if not have_privilege(request.user, x, CAN_READ):
            return abort_access_denied(request)
        try:
            s = Subscription.objects.get(user=request.user, **{subscriptionkw : x.id})
        except Subscription.DoesNotExist:
            # there's no such subscription yet, create a new one
            Subscription(user=request.user,**{subscriptionkw : x.id}).save()
            flash(flasher)
        return HttpResponseRedirect(url_for(x))
    return subscriber


def _generate_unsubscriber(obj, obj_slug, subscriptionkw, flasher):
    """
    Generates an unsubscriber-function to deal with objects of type `obj`
    which have the slug `slug` and are registered in the subscribtion by
    `subscriptionkw` and have the flashing-test `flasher`
    """
    if subscriptionkw in ('forum', 'topic'):
        subscriptionkw = subscriptionkw + '_id'
    @simple_check_login
    def subscriber(request, **kwargs):
        """ If the user has already subscribed to this %s, this view removes it.
        """ % obj_slug
        slug = kwargs[obj_slug]
        x = obj.query.filter(obj.slug==slug).one()
        if not have_privilege(request.user, x, CAN_READ):
            return abort_access_denied(request)
        try:
            s = Subscription.objects.get(user=request.user, **{subscriptionkw : x.id})
        except Subscription.DoesNotExist:
            pass
        else:
            # there's already a subscription for this forum, remove it
            s.delete()
            flash(flasher)
        return HttpResponseRedirect(url_for(x))
    return subscriber

subscribe_forum = _generate_subscriber(Forum,
    'slug', 'forum',
    (u'Du wirst ab nun bei neuen Themen in diesem Forum '
     u'benachrichtigt'))


unsubscribe_forum = _generate_unsubscriber(Forum,
    'slug', 'forum',
    (u'Du wirst ab nun bei neuen Themen in diesem Forum nicht '
              u' mehr benachrichtigt'))

subscribe_topic = _generate_subscriber(Topic,
    'topic_slug', 'topic',
    (u'Du wirst ab jetzt bei neuen Beiträgen in diesem Thema '
              u'benachrichtigt.'))

unsubscribe_topic = _generate_unsubscriber(Topic,
    'topic_slug', 'topic',
    (u'Du wirst ab nun bei neuen Beiträgen in diesem Thema nicht '
              u'mehr benachrichtigt'))


@simple_check_login
@templated('forum/report.html')
def report(request, topic_slug):
    """Change the report_status of a topic and redirect to it"""
    t = Topic.query.filter_by(slug=topic_slug).first()
    if not t:
        raise PageNotFound
    if not have_privilege(request.user, t.forum, CAN_READ):
        return abort_access_denied(request)
    if t.reported:
        flash(u'Dieses Thema wurde bereits gemeldet; die Moderatoren werden '
              u'sich in Kürze darum kümmern.')
        return HttpResponseRedirect(t.get_absolute_url())

    if request.method == 'POST':
        form = ReportTopicForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            t.reported = d['text']
            t.reporter_id = request.user.id
            session.commit()
            cache.delete('forum/reported_topic_count')
            flash(u'Dieses Thema wurde den Moderatoren gemeldet. '
                  u'Sie werden sich sobald wie möglich darum kümmern', True)
            return HttpResponseRedirect(t.get_absolute_url())
    else:
        form = ReportTopicForm()
    return {
        'topic': t,
        'form':  form
    }


@templated('forum/reportlist.html')
def reportlist(request):
    """Get a list of all reported topics"""
    def _add_field_choices():
        """Add dynamic field choices to the reported topic formular"""
        form.fields['selected'].choices = [(t.id, u'') for t in topics]

    topics = Topic.query.filter(Topic.reported != None)
    if request.method == 'POST':
        form = ReportListForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            d = form.cleaned_data
            session.execute(topic_table.update(
                topic_table.c.id.in_(d['selected']), values={
                    'reported': None,
                    'reporter_id': None
            }))
            session.commit()
            cache.delete('forum/reported_topic_count')
            topics = filter(lambda t: str(t.id) not in d['selected'], topics)
            flash(u'Die gewählten Themen wurden als bearbeitet markiert.',
                  True)
    else:
        form = ReportListForm()
        _add_field_choices()

    privileges = get_privileges(request.user, [x.forum_id for x in topics])
    visible_topics = filter(lambda t: have_privilege(request.user, t.forum,
                            CAN_MODERATE), topics)

    return {
        'topics':   visible_topics,
        'form':     form
    }


def post(request, post_id):
    """Redirect to the "real" post url" (see `PostManager.url_for_post`)"""
    url = Post.url_for_post(int(post_id),
        paramstr=request.GET and request.GET.urlencode())
    if not url:
        raise PageNotFound()
    return HttpResponseRedirect(url)


@templated('forum/movetopic.html')
def movetopic(request, topic_slug):
    """Move a topic into another forum"""
    def _add_field_choices():
        """Add dynamic field choices to the move topic formular"""
        form.fields['forum_id'].choices = [(f.id, f.name) for f in forums]

    t = Topic.query.filter_by(slug=topic_slug).first()
    if not t:
        raise PageNotFound
    if not have_privilege(request.user, t.forum, CAN_MODERATE):
        return abort_access_denied(request)

    forums = filter_invisible(request.user, Forum.query.filter(and_(
        Forum.c.parent_id != None, Forum.c.id != t.forum_id)))
    mapping = dict((x.id, x) for x in forums)
    if not mapping:
        return abort_access_denied(request)

    if request.method == 'POST':
        form = MoveTopicForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            data = form.cleaned_data
            f = mapping.get(int(data['forum_id']))
            if f is None:
                return abort_access_denied(request)
            t.move(f)
            session.commit()
            # send a notification to the topic author to inform him about
            # the new forum.
            nargs = {
                'username':   t.author.username,
                'topic':      t,
                'mod':        request.user.username,
                'forum_name': f.name
            }
            if 'topic_move' in t.author.settings.get('notifications',
                                                     ('topic_move',)):
                send_notification(t.author, 'topic_moved',
                    u'Dein Thema „%s“ wurde verschoben' % t.title, nargs)

            subscribers = Subscription.objects.filter(topic=t)
            for user in subscribers:
                send_notification(user, 'topic_moved',
                    u'Das Thema „%s“ wurde verschoben' % t.title, nargs)
            return HttpResponseRedirect(t.get_absolute_url())
    else:
        form = MoveTopicForm()
        _add_field_choices()
    return {
        'form':  form,
        'topic': t
    }


@templated('forum/splittopic.html')
def splittopic(request, topic_slug):
    def _add_field_choices():
        """Add dynamic field choices to the split topic formular"""
        form.fields['forum'].choices = [(f.id, f.name) for f in
            Forum.query.filter(Forum.c.parent_id != None)]
        form.fields['start'].choices = form.fields['select'].choices = \
            [(p.id, u'') for p in posts]

    t = Topic.query.options(eagerload('posts')).filter_by(slug=topic_slug).first()
    if not t:
        raise PageNotFound
    posts = t.posts
    if not have_privilege(request.user, t.forum, CAN_MODERATE):
        return abort_access_denied(request)

    if request.method == 'POST':
        form = SplitTopicForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            data = form.cleaned_data
            if data['select_following']:
                p = Post.query.filter(and_(
                    Post.c.topic_id==t.id, Post.c.id >= data['start']))
            else:
                p = Post.query.filter(Post.c.id.in_(data['select']))

            if data['action'] == 'new':
                new = Post.split(p, data['forum'], title=data['title'])
            else:
                new = Post.split(p, topic_slug=data['topic_slug'])
            return HttpResponseRedirect(new.get_absolute_url())
    else:
        form = SplitTopicForm()
        _add_field_choices()

    return {
        'topic': t,
        'forum': t.forum,
        'posts': posts,
        'form':  form
    }


def hide_post(request, post_id):
    """
    Sets the hidden flag of a post to True which has the effect that normal
    users can't see it anymore (moderators still can).
    """
    # XXX: Thanks to the join we need post_id twice now, as sa thinks there are two?
    post = Post.query.get((post_id, post_id))
    if not post:
        raise PageNotFound
    if not have_privilege(request.user, post.topic.forum, CAN_MODERATE):
        return abort_access_denied(request)
    if post.id == post.topic.first_post_id:
        flash(u'Der erste Beitrag eines Themas darf nicht unsichtbar gemacht '
              u'werden.')
    else:
        post.hidden = True
        session.commit()
        flash(u'Der Beitrag von „<a href="%s">%s</a>“ wurde unsichtbar '
              u'gemacht.' % (url_for(post), escape(post.author.username)),
              success=True)
    return HttpResponseRedirect(url_for(post).split('#')[0])


def restore_post(request, post_id):
    """
    This function removes the hidden flag of a post to make it visible for
    normal users again.
    """
    # XXX: Thanks to the join we need post_id twice now, as sa thinks there are two?
    post = Post.query.get((post_id, post_id))
    if not post:
        raise PageNotFound
    if not have_privilege(request.user, post.topic.forum, CAN_MODERATE):
        return abort_access_denied(request)
    post.hidden = False
    session.commit()
    flash(u'Der Beitrag von „<a href="%s">%s</a>“ wurde wieder sichtbar '
          u'gemacht.' % (url_for(post), escape(post.author.username)),
          success=True)
    return HttpResponseRedirect(url_for(post).split('#')[0])


def delete_post(request, post_id):
    """
    In contrast to `hide_post` this function does really remove this post.
    This action is irrevocable and can only get executed by moderators.
    """
    post = Post.query.get(post_id)
    if not post:
        raise PageNotFound
    if not have_privilege(request.user, post.topic.forum, CAN_MODERATE):
        return abort_access_denied(request)
    if post.id == post.topic.first_post.id:
        flash(u'Der erste Beitrag eines Themas darf nicht gelöscht werden.',
              success=False)
    else:
        if request.method == 'POST':
            if 'cancel' in request.POST:
                flash(u'Das löschen wurde abgebrochen.')
            else:
                session.delete(post)
                session.commit()
                flash(u'Der Beitrag von „<a href="%s">%s</a>“ wurde gelöscht.'
                      % (url_for(post), escape(post.author.username)),
                      success=True)
        else:
            flash(render_template('forum/post_delete.html', {'post': post}))
    return HttpResponseRedirect(url_for(post.topic))


@templated('forum/revisions.html')
def revisions(request, post_id):
    revs = PostRevision.query.options(eagerload('post'),
            eagerload('post.topic'), eagerload('post.topic.forum')) \
        .filter(PostRevision.post_id == post_id)
    if not have_privilege(request.user, revs[0].post.topic.forum, CAN_MODERATE):
        return abort_access_denied(request)
    return {
        'revisions': list(revs)
    }


def restore_revision(request, rev_id):
    rev = PostRevision.query.options(eagerload('post'),
        eagerload('post.topic'), eagerload('post.topic.forum')).get(rev_id)
    if not have_privilege(request.user, rev.post.topic.forum, CAN_MODERATE):
        return abort_access_denied(request)
    rev.restore(request)
    session.commit()
    flash(u'Eine alte Version des Beitrags wurde wiederhergestellt.', True)
    return HttpResponseRedirect(href('forum', 'post', rev.post_id))


def hide_topic(request, topic_slug):
    """
    Sets the hidden flag of a topic to True which has the effect that normal
    users can't see it anymore (moderators still can).
    """
    topic = Topic.query.filter_by(slug=topic_slug).first()
    if not topic:
        raise PageNotFound
    if not have_privilege(request.user, topic.forum, CAN_MODERATE):
        return abort_access_denied(request)
    topic.hidden = True
    session.commit()
    flash(u'Das Thema „%s“ wurde unsichtbar gemacht.' % topic.title,
          success=True)
    topic.forum.invalidate_topic_cache()
    return HttpResponseRedirect(url_for(topic))


def restore_topic(request, topic_slug):
    """
    This function removes the hidden flag of a topic to make it visible for
    normal users again.
    """
    topic = Topic.query.filter_by(slug=topic_slug).first()
    if not topic:
        raise PageNotFound
    if not have_privilege(request.user, topic.forum, CAN_MODERATE):
        return abort_access_denied(request)
    topic.hidden = False
    session.commit()
    flash(u'Das Thema „%s“ wurde wieder sichtbar gemacht.' % topic.title,
          success=True)
    return HttpResponseRedirect(url_for(topic))


def delete_topic(request, topic_slug):
    """
    In contrast to `hide_topic` this function does really remove the topic.
    This action is irrevocable and can only get executed by administrators.
    """
    # XXX: Only administrators are allowed to do this, not moderators
    topic = Topic.query.filter_by(slug=topic_slug).first()
    if not topic:
        raise PageNotFound
    if not have_privilege(request.user, topic.forum, CAN_MODERATE):
        return abort_access_denied(request)

    if request.method == 'POST':
        if 'cancel' in request.POST:
            flash(u'Löschen des Themas „%s“ wurde abgebrochen' % topic.title)
        else:
            redirect = url_for(topic.forum)
            session.delete(topic)
            flash(u'Das Thema „%s“ wurde erfolgreich gelöscht' % topic.title,
                  success=True)
            session.commit()
            return HttpResponseRedirect(redirect)
    else:
        flash(render_template('forum/delete_topic.html', {'topic': topic}))
    topic.forum.invalidate_topic_cache()
    return HttpResponseRedirect(url_for(topic))


@does_not_exist_is_404
def feed(request, component='forum', slug=None, mode='short', count=20):
    """
    Show the feeds for the forum.

    For every combination of component, slug and mode a cache item with 100
    entries generated, and it then truncated to `count` entries.  This cache
    is only invalidated after some time, not everytime something changes, so
    the feeds are always ~5 minutes delayed.
    """

    if component not in ('forum', 'topic'):
        raise PageNotFound

    if mode not in ('full', 'short', 'title'):
        raise PageNotFound

    count = int(count)
    if count not in (10, 20, 30, 50, 75, 100):
        raise PageNotFound

    anonymous = User.objects.get_anonymous_user()

    # key = 'forum/feeds/%s/%s/%s/%s' % (component, slug, mode, count)
    # content = cache.get(key)
    # if content is not None:
    #     content_type='application/atom+xml; charset=utf-8'
    #     return HttpResponse(content, content_type=content_type)

    if component == 'topic':
        topic = Topic.query.filter_by(slug=slug).one()
        if topic is None:
            raise PageNotFound
        if not have_privilege(anonymous, topic.forum, CAN_READ):
            return abort_access_denied(request)
        if topic.hidden:
            raise PageNotFound

        cache_key = 'forum/feeds/topic/%s/%s' % (slug, mode)
        feed = cache.get(cache_key)
        if feed is None:
            posts = topic.posts.order_by(Post.pub_date.desc())[:100]

            feed = FeedBuilder(
                title=u'ubuntuusers Thema – „%s“' % topic.title,
                url=url_for(topic),
                feed_url=request.build_absolute_uri(),
                rights=href('portal', 'lizenz'),
            )

            for post in posts:
                kwargs = {}
                if mode == 'full':
                    kwargs['content'] = u'<div xmlns="http://www.w3.org/1999/' \
                                        u'xhtml">%s</div>' % post.rendered_text
                    kwargs['content_type'] = 'xhtml'
                if mode == 'short':
                    summary = truncate_html_words(post.rendered_text, 100)
                    kwargs['summary'] = u'<div xmlns="http://www.w3.org/1999/' \
                                        u'xhtml">%s</div>' % summary
                    kwargs['summary_type'] = 'xhtml'

                feed.add(
                    title='%s (%s)' % (
                        post.author.username,
                        format_datetime(post.pub_date)
                    ),
                    url=url_for(post),
                    author=post.author,
                    published=post.pub_date,
                    updated=post.pub_date,
                    **kwargs
                )

    else:
        must_create = False
        if slug:
            forum = Forum.query.get(slug)
            if forum is None:
                raise PageNotFound
            if not have_privilege(anonymous, forum, CAN_READ):
                return abort_access_denied(request)

            cache_key = 'forum/feeds/forum/%s/%s' % (slug, mode)
            feed = cache.get(cache_key)
            if feed is None:
                topics = forum.get_latest_topics()
                feed = FeedBuilder(
                    title=u'ubuntuusers Forum – „%s“' % forum.name,
                    url=url_for(forum),
                    feed_url=request.build_absolute_uri(),
                    rights=href('portal', 'lizenz'),
                )
                must_create = True

        else:
            cache_key = 'forum/feeds/forum/*/%s' % (mode)
            feed = cache.get(cache_key)
            if feed is None:
                topics = Topic.query.order_by(Topic.id.desc())[:100]
                feed = FeedBuilder(
                    title=u'ubuntuusers Forum',
                    url=href('forum'),
                    feed_url=request.build_absolute_uri(),
                    rights=href('portal', 'lizenz'),
                )
                must_create = True

        if must_create:
            for topic in topics:
                kwargs = {}
                post = topic.first_post

                #XXX: this way there might be less than `count` items
                if not have_privilege(anonymous, topic.forum, CAN_READ):
                    continue
                if topic.hidden:
                    continue

                if post.rendered_text is None:
                    post.render_text()
                rendered_text = post.rendered_text
                if mode == 'full':
                    kwargs['content'] = u'<div xmlns="http://www.w3.org/1999/' \
                                        u'xhtml">%s</div>' % rendered_text
                    kwargs['content_type'] = 'xhtml'
                if mode == 'short':
                    summary = truncate_html_words(rendered_text, 100)
                    kwargs['summary'] = u'<div xmlns="http://www.w3.org/1999/' \
                                        u'xhtml">%s</div>' % summary
                    kwargs['summary_type'] = 'xhtml'

                feed.add(
                    title=topic.title,
                    url=url_for(topic),
                    author={
                        'name': topic.author.username,
                        'uri': topic.author.get_absolute_url(),
                    },
                    published=post.pub_date,
                    updated=post.pub_date,
                    **kwargs
                )

    feed.truncate(count)
    cache.set(cache_key, feed, 600)
    return feed.get_atom_response()


    # response = feed.get_atom_response()
    # cache.set(key, response.content, 600)
    # return response


def markread(request, slug=None):
    """
    Mark either all or only the given forum as read.
    """
    user = request.user
    if user.is_anonymous:
        return
    if slug:
        forum = Forum.query.get(slug)
        if not forum:
            raise PageNotFound()
        forum.mark_read(user)
        user.save()
        flash(u'Das Forum „%s“ wurde als gelesen markiert.' % forum.name)
        return HttpResponseRedirect(url_for(forum))
    else:
        category_ids = session.execute(select([forum_table.c.id],
            forum_table.c.parent_id == None)).fetchall()
        for row in category_ids:
            Forum.query.get(row[0]).mark_read(user)
        user.save()
        flash(u'Allen Foren wurden als gelesen markiert.')
    return HttpResponseRedirect(href('forum'))


@templated('forum/newposts.html')
def newposts(request, page=1):
    """
    Return a list of the latest posts.
    """
    # TODO: This shows hidden topics to everyone
    forum_ids = [f[0] for f in select([forum_table.c.id]).execute()]
    privs = get_privileges(request.user, forum_ids)
    all_topics = cache.get('forum/lasttopics')
    if not all_topics:
        all_topics = list(Topic.query.options(eagerload('author'), \
            eagerload('last_post'), eagerload('last_post.author')) \
            .order_by((topic_table.c.last_post_id.desc()))[:80])
        cache.set('forum/lasttopics', all_topics)
    topics = []
    for topic in all_topics:
        if topic.last_post_id < request.user.forum_last_read:
            break
        if check_privilege(privs.get(topic.forum_id, {}), CAN_READ):
            topics.append(topic)
    pagination = Pagination(request, topics, page, 20,
        href('forum', 'newposts'))
    return {
        'topics':     list(pagination.objects),
        'pagination': pagination,
        'get_read_status':  lambda post_id: request.user.is_authenticated \
                  and request.user._readstatus(forum_id=f.id, post_id=post_id)
    }


@templated('forum/topiclist.html')
def topiclist(request, page=1, action='newposts', hours=24, user=None):
    hours = int(hours)
    user = user and User.objects.get(username=user) or request.user

    topics = Topic.query.order_by(topic_table.c.last_post_id.desc())

    if action == 'last':
        topics = topics.filter(and_(
            topic_table.c.last_post_id == post_table.c.id,
            post_table.c.pub_date > datetime.now() - timedelta(hours=hours)
        ))
        title = u'Beiträge der letzten %d Stunden' % hours
        url = href('forum', 'last%d' % hours)
    elif action == 'unanswered':
        topics = topics.filter(Topic.post_count == 1)
        title = u'Unbeantwortete Themen'
        url = href('forum', 'unanswered')
    elif action == 'unsolved':
        topics = topics.filter(Topic.solved == False)
        title = u'Ungelöste Themen'
        url = href('forum', 'unsolved')
    elif action == 'author':
        topics = topics.filter(topic_table.c.id.in_(post_table.c.topic_id)) \
                       .filter(post_table.c.author_id == user.id)
        if user != request.user:
            title = u'Beiträge von „%s“' % escape(user.username)
            url = href('forum', user.username)
        else:
            title = u'Eigene Beiträge'
            url = href('forum', 'egosearch')

    # TODO: eagerload('last_post'), eagerload('last_post.author') raises
    #       an error.
    topics = topics.options(eagerload('author'))

    pagination = Pagination(request, topics, page, TOPICS_PER_PAGE, url)

    return {
        'topics':       list(pagination.objects),
        'pagination':   pagination.generate(),
        'title':        title,
        'get_read_status':  lambda post_id: request.user.is_authenticated \
                  and request.user._readstatus(post_id=post_id)
    }


@templated('forum/welcome.html')
def welcome(request, slug, path=None):
    """
    Show a welcome message on the first visit to greet the users or
    inform him about special rules.
    """
    user = request.user
    forum = Forum.objects.get(slug=slug)
    if not forum.welcome_message:
        raise PageNotFound()
    goto_url = path or url_for(forum)
    if request.method == 'POST':
        accepted = request.POST.get('accept', False)
        forum.read_welcome(request.user, accepted)
        if accepted:
            return HttpResponseRedirect(request.POST.get('goto_url'))
        else:
            return HttpResponseRedirect(href('forum'))
    return {
        'goto_url': goto_url,
        'message': forum.welcome_message,
        'forum': forum
    }
