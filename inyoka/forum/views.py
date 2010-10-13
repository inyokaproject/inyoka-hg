# -*- coding: utf-8 -*-
"""
    inyoka.forum.views
    ~~~~~~~~~~~~~~~~~~

    The views for the forum.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import re
from datetime import datetime, timedelta
from operator import attrgetter

from django.utils.text import truncate_html_words
from django.db import transaction
from django.db.models import Q
from django.forms.util import ErrorDict
from sqlalchemy.orm import eagerload
from sqlalchemy.sql import and_, select
from sqlalchemy.exceptions import InvalidRequestError, OperationalError

from inyoka.conf import settings
from inyoka.utils.urls import global_not_found, href, url_for, is_safe_domain
from inyoka.utils.html import escape
from inyoka.utils.text import normalize_pagename
from inyoka.utils.sessions import set_session_info
from inyoka.utils.http import templated, PageNotFound, HttpResponseRedirect
from inyoka.utils.feeds import FeedBuilder, atom_feed
from inyoka.utils.flashing import flash
from inyoka.utils.templating import render_template
from inyoka.utils.pagination import Pagination
from inyoka.utils.notification import send_notification, notify_about_subscription
from inyoka.utils.collections import flatten_iterator
from inyoka.utils.cache import cache
from inyoka.utils.dates import format_datetime
from inyoka.utils.database import db
from inyoka.utils.storage import storage
from inyoka.wiki.utils import quote_text
from inyoka.wiki.parser import parse, RenderContext
from inyoka.wiki.models import Page
from inyoka.portal.utils import simple_check_login, abort_access_denied, \
    require_permission
from inyoka.portal.user import User
from inyoka.portal.models import Subscription
from inyoka.forum.models import Forum, Topic, POSTS_PER_PAGE, Post, Poll, \
    TOPICS_PER_PAGE, PollVote, PollOption, Attachment, PostRevision, \
    CACHE_PAGES_COUNT, WelcomeMessage, fix_plaintext, Privilege
from inyoka.forum.compat import SAUser
from inyoka.forum.forms import NewTopicForm, SplitTopicForm, EditPostForm, \
    AddPollForm, MoveTopicForm, ReportTopicForm, ReportListForm, \
    AddAttachmentForm
from inyoka.forum.acl import filter_invisible, get_forum_privileges, \
    have_privilege, CAN_READ, CAN_MODERATE, \
    check_privilege

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
    is_index = category is None
    if is_index:
        session_info = (u'sieht sich die Forenübersicht an.',
                        u'Forenübersicht')
    else:
        session_info = ((u'sieht sich die Forenübersicht der '
                            u'Kategorie „%s“ an' % category),
                        u'Kategorieübersicht')

    forums = Forum.query.get_forums_filtered(request.user, sort=True)

    if category:
        category = Forum.query.get_cached(category)
        if not category or category.parent_id != None:
            raise PageNotFound()
        category = category

        if have_privilege(User.ANONYMOUS_USER, category, 'read'):
            set_session_info(request, *session_info)
        categories = [category]

        fmsg = category.find_welcome(request.user)
        if fmsg is not None:
            return welcome(request, fmsg.slug, request.path)
    else:
        categories = tuple(forum for forum in forums if forum.parent_id == None)
        # forum-overview can be set without any acl check ;)
        set_session_info(request, *session_info)

    hidden_categories = []
    if request.user.is_authenticated:
        hidden_categories.extend(request.user.settings.get(
            'hidden_forum_categories', ())
        )

    forum_hierarchy = []
    for category in categories:
        category_forums = []
        for forum in category.filter_children(forums):
            category_forums.append((forum, forum.filter_children(forums)))
        forum_hierarchy.append((category, category_forums))

    return {
        'categories':           categories,
        'is_index':             is_index,
        'hidden_categories':    hidden_categories,
        'forum_hierarchy':      forum_hierarchy,
    }


@templated('forum/forum.html')
def forum(request, slug, page=1):
    """
    Return a single forum to show a topic list.
    """
    forum = Forum.query.get(slug)
    # if the forum is a category we raise PageNotFound. Categories have
    # their own url at /category.
    if not forum or forum.parent_id is None:
        raise PageNotFound()

    privs = get_forum_privileges(request.user, forum.id)
    if not check_privilege(privs, 'read'):
        return abort_access_denied(request)

    fmsg = forum.find_welcome(request.user)
    if fmsg is not None:
        return welcome(request, fmsg.slug, request.path)

    #TODO: move that cache logic to model
    if page < CACHE_PAGES_COUNT:
        key = 'forum/topics/%d/%d' % (forum.id, int(page))
        ctx = cache.get(key)
    else:
        ctx = None

    if ctx is None:
        topic_ids = db.session.query(Topic.id) \
                              .filter_by(forum_id=forum.id) \
                              .order_by(Topic.sticky.desc(), Topic.last_post_id.desc())
        pagination = Pagination(request, topic_ids, page, TOPICS_PER_PAGE, url_for(forum))
        required_ids = [obj.id for obj in pagination.objects]
        topics = Topic.query.filter_overview(forum.id).filter(Topic.id.in_(required_ids)).all()

        ctx = {
            'topics':           topics,
            'pagination_left':  pagination.generate(),
            'pagination_right': pagination.generate('right')
        }

        if page < CACHE_PAGES_COUNT:
            cache.set(key, ctx, 60)
    else:
        merge = db.session.merge
        ctx['topics'] = [merge(obj, load=False) for obj in ctx['topics']]


    if have_privilege(User.ANONYMOUS_USER, forum, 'read'):
        set_session_info(request, u'sieht sich das Forum „<a href="%s">'
                         u'%s</a>“ an' % (escape(url_for(forum)), escape(forum.name)),
                         'besuche das Forum')

    supporters = cache.get('forum/forum/supporters-%s' % forum.id)
    if supporters is None:
        supporters = []
        query = db.session.query(Privilege.user_id, Privilege.positive) \
                          .filter(db.and_(Privilege.forum_id == forum.id,
                                          Privilege.user_id != None)).all()
        subset = [r.user_id for r in query if check_privilege(r.positive, 'moderate')]
        if subset:
            supporters = SAUser.query.filter(SAUser.id.in_(subset)) \
                                     .order_by(SAUser.username).all()
        cache.set('forum/forum/supporters-%s' % forum.id, supporters, 86400)
    else:
        merge = db.session.merge
        supporters = [merge(obj, load=False) for obj in supporters]

    ctx.update({
        'forum':         forum,
        'subforums':     filter_invisible(request.user, forum.children),
        'is_subscribed': Subscription.objects.user_subscribed(request.user,
                                                              forum=forum),
        'can_moderate':  check_privilege(privs, 'moderate'),
        'can_create':    check_privilege(privs, 'create'),
        'supporters':     supporters
    })
    return ctx


@transaction.autocommit
@templated('forum/topic.html')
def viewtopic(request, topic_slug, page=1):
    """
    Shows a topic, the posts are paginated.
    If the topic has a `hidden` flag, the user gets a nice message that the
    topic is deleted and is redirected to the topic's forum.  Moderators can
    see these topics.
    """
    try:
        t = Topic.query.filter_by(slug=topic_slug).one()
    except db.NoResultFound:
        raise PageNotFound('no such topic')
    privileges = get_forum_privileges(request.user, t.forum_id)
    if not check_privilege(privileges, 'read'):
        return abort_access_denied(request)
    if t.hidden:
        if not check_privilege(privileges, 'moderate'):
            flash(u'Dieses Thema wurde von einem Moderator gelöscht.')
            return HttpResponseRedirect(url_for(t.cached_forum()))
        flash(u'Dieses Thema ist unsichtbar für normale Benutzer.')
    fmsg = t.cached_forum().find_welcome(request.user)
    if fmsg is not None:
        return welcome(request, fmsg.slug, request.path)
    t.touch()

    discussions = Page.objects.filter(topic_id=t.id)

    posts = t.posts.options(db.eagerload_all('author.groups'),
                            db.eagerload('attachments')) \
                   .order_by(Post.position)

    if t.has_poll:
        polls = Poll.query.options(eagerload('options')).filter(
            Poll.topic_id==t.id).all()

        if request.method == 'POST':
            if not check_privilege(privileges, 'vote'):
                return abort_access_denied(request)
            # the user participated in a poll
            for poll in polls:
                # get the votes for every poll in this topic
                if poll.multiple_votes:
                    votes = request.POST.getlist('poll_%s' % poll.id)
                else:
                    vote = request.POST.get('poll_%s' % poll.id)
                    votes = vote and [vote] or []
                if votes:
                    if poll.participated:
                        continue
                    elif poll.ended:
                        flash(u'Die Abstimmung ist bereits zu Ende.', False)
                        continue
                    poll.votings.append(PollVote(voter_id=request.user.id))
                    db.session.execute(PollOption.__table__.update(
                        PollOption.id.in_(votes) &
                        (PollOption.poll_id == poll.id), values={
                            'votes': PollOption.votes + 1
                    }))
                    flash(u'Deine Stimme wurde gespeichert.', True)
            db.session.commit()
            for poll in polls:
                for option in poll.options:
                    db.session.refresh(option)

    else:
        polls = None

    pagination = Pagination(request, posts, page, POSTS_PER_PAGE, url_for(t),
                     total=t.post_count, rownum_column=Post.position)

    if have_privilege(User.ANONYMOUS_USER, t, 'read'):
        set_session_info(request, u'sieht sich das Thema „<a href="%s">%s'
            u'</a>“ an' % (url_for(t), escape(t.title)), 'besuche Thema')

    subscribed = True
    if request.user.is_authenticated:
        t.mark_read(request.user)
        request.user.save()
        try:
            subscription = Subscription.objects \
                .filter(user=request.user, topic_id=t.id).get()
            subscription.notified = False
            subscription.save()
        except Subscription.DoesNotExist:
            subscribed = False

    post_objects = pagination.objects.all()

    for post in post_objects:
        if not post.rendered_text and not post.is_plaintext:
            try:
                post.rendered_text = post.render_text(force_existing=True)
                db.session.commit()
            except OperationalError:
                pass

    team_icon = storage['team_icon']

    if team_icon:
        team_icon = href('media', storage['team_icon'])
    else:
        team_icon = None

    can_mod = check_privilege(privileges, 'moderate')
    can_reply = check_privilege(privileges, 'reply')
    can_vote = check_privilege(privileges, 'vote')
    can_edit = lambda post: post.author_id == request.user.id and \
        can_reply and post.check_ownpost_limit('edit')
    can_delete = lambda post: can_reply and post.author_id == request.user.id \
        and post.check_ownpost_limit('delete')
    voted_all = not (polls and bool([True for p in polls if p.can_vote]))

    return {
        'topic':             t,
        'forum':             t.cached_forum(),
        'posts':             post_objects,
        'is_subscribed':     subscribed,
        'pagination':        pagination,
        'polls':             polls,
        'show_vote_results': request.GET.get('action') == 'vote_results',
        'voted_all':         voted_all,
        'can_moderate':      can_mod,
        'can_edit':          can_edit,
        'can_reply':         can_reply,
        'can_vote':          can_vote,
        'can_delete':        can_delete,
        'team_icon_url':     team_icon,
        'discussions':       discussions,
    }


@transaction.autocommit
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
    post = topic = forum = attachment = quote = posts = discussions = None
    newtopic = firstpost = False
    poll_form = poll_options = polls = None
    attach_form = None
    attachments = []
    preview = None
    article = None

    if article_name:
        try:
            article = Page.objects.get(name=normalize_pagename(article_name))
        except Page.DoesNotExist:
            flash(u'Der Artikel „%s“ existiert nicht. Du kannst ihn nun anlegen'
                  % normalize_pagename(article_name), False)
            return HttpResponseRedirect(href('wiki',
                                             normalize_pagename(article_name)))
        forum_slug = settings.WIKI_DISCUSSION_FORUM
        flash(u'Zu dem Artikel „%s“ existiert noch keine Diskussion. '
              u'Wenn du willst, kannst du hier eine neue anlegen, oder '
              u'<a href="%s">ein bestehendes Thema als Diskussion auswählen</a>.' % (
                  escape(article_name),
                  href('wiki', normalize_pagename(article_name),
                       action='manage_discussion'),
              ))
    if topic_slug:
        try:
            topic = Topic.query.filter_by(slug=topic_slug).one()
        except InvalidRequestError:
            raise PageNotFound()
        if not topic:
            raise PageNotFound()
        forum = topic.forum
    elif forum_slug:
        forum = Forum.query.get_cached(slug=forum_slug)
        if not forum or not forum.parent_id:
            raise PageNotFound()
        newtopic = firstpost = True
    elif post_id:
        post = Post.query.get(post_id)
        if not post:
            raise PageNotFound()
        topic = post.topic
        forum = topic.forum
        firstpost = post.id == topic.first_post_id
    elif quote_id:
        quote = Post.query.options(eagerload('topic'), eagerload('author')) \
                          .get(quote_id)
        if not quote:
            raise PageNotFound()
        topic = quote.topic
        forum = topic.forum
    if newtopic:
        form = NewTopicForm(request.POST or None, initial={
            'text':  forum.newtopic_default_text,
            'title': article and article.name or '',
        }, force_version=forum.force_version)
    elif quote:
        form = EditPostForm(request.POST or None, initial={
            'text': quote_text(quote.text, quote.author) + '\n',
        })
    else:
        form = EditPostForm(request.POST or None)

    # check privileges
    privileges = get_forum_privileges(request.user, forum.id)
    if post:
        if (topic.locked or topic.hidden or post.hidden) and \
           not check_privilege(privileges, 'moderate'):
            flash(u'Du darfst diesen Beitrag nicht bearbeiten!', False)
            return HttpResponseRedirect(href('forum', 'topic', post.topic.slug,
                                         post.page))
        if not (check_privilege(privileges, 'moderate') or
                (post.author_id == request.user.id and
                 check_privilege(privileges, 'reply') and
                 post.check_ownpost_limit('edit'))):
            flash(u'Du darfst diesen Beitrag nicht bearbeiten!', False)
            return HttpResponseRedirect(href('forum', 'topic', post.topic.slug,
                                             post.page))
    elif topic:
        if topic.locked:
            if not check_privilege(privileges, 'moderate'):
                flash(u'Du kannst auf in diesem Thema nicht antworten, da es '
                      u'von einem Moderator geschlossen wurde.', False)
                return HttpResponseRedirect(url_for(topic))
            else:
                flash(u'Du antwortest auf einen bereits geschlossenen Thread. '
                      u'Dies wird oft als unhöflich aufgefasst, bitte sei dir '
                      u'dessen bewusst!', False)
        elif topic.hidden:
            if not check_privilege(privileges, 'moderate'):
                flash(u'Du kannst auf in diesem Thema nicht antworten, da es '
                      u'von einem Moderator gelöscht wurde.', False)
                return HttpResponseRedirect(url_for(topic))
        else:
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

    # Cleanup errors in parent form if the main form was not send.
    # This fixes some nasty things if someone adds just an attachment
    # or a poll.
    if request.method == 'POST' and not 'send' in request.POST:
        # clean errors in parent form so that adding a poll
        # does not raise any errors.  We also cleanup the surge
        # protection timer so that we get no nasty hickups by just
        # adding an attachment and sending the whole form
        # afterwards.
        form.errors.clear()
        if 'sp' in request.session:
            del request.session['sp']

    #  handle polls
    poll_ids = map(int, filter(bool, request.POST.get('polls', '').split(',')))
    if (newtopic or firstpost) and check_privilege(privileges, 'create_poll'):
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
            db.session.commit()
            if topic:
                topic.has_poll = True
                db.session.commit()
                topic.forum.invalidate_topic_cache()
            poll_form = AddPollForm()
            poll_options = ['', '']
            flash(u'Die Umfrage "%s" wurde hinzugefügt' % poll.question, True)
            poll_ids.append(poll.id)
        elif 'add_option' in request.POST:
            poll_options.append('')

        elif 'delete_poll' in request.POST:
            poll = Poll.query.filter_by(id=request.POST['delete_poll'],
                topic=topic).first()
            if poll is not None:
                flash(u'Die Umfrage "%s" wurde gelöscht' % poll.question)
                topic.has_poll = bool(db.session.execute(select([1],
                    (Poll.topic_id == topic.id) & (Poll.id != poll.id)) \
                    .limit(1)).fetchone())
                db.session.delete(poll)
                db.session.commit()
                topic.forum.invalidate_topic_cache()
        polls = []
        if poll_ids:
            polls = Poll.query.filter(db.or_(
                Poll.id.in_(poll_ids),
                Poll.topic_id == (topic and topic.id or -1)
            )).all()

    # handle attachments
    att_ids = map(int, filter(bool,
        request.POST.get('attachments', '').split(',')
    ))
    if check_privilege(privileges, 'upload'):
        # check for post = None to be sure that the user can't "hijack"
        # other attachments.
        if att_ids:
            attachments = Attachment.query.filter(and_(
                Attachment.id.in_(att_ids),
                Attachment.post_id == bool(post)==True and post.id or None
            )).all()
        else:
            attachments = []
        if 'attach' in request.POST:
            attach_form = AddAttachmentForm(request.POST, request.FILES)
        else:
            attach_form = AddAttachmentForm()

        if 'attach' in request.POST:
            # the user uploaded a new attachment
            if attach_form.is_valid():
                d = attach_form.cleaned_data
                att_name = (d.get('filename') or d['attachment'].name)
                attachment = Attachment.create(
                    att_name, d['attachment'].read(),
                    request.FILES['attachment'].content_type,
                    attachments, override=d['override']
                )
                if not attachment:
                    flash(u'Ein Anhang „%s“ existiert bereits' % att_name, False)
                else:
                    attachment.comment = d['comment']
                    db.session.commit()
                    attachments.append(attachment)
                    att_ids.append(attachment.id)
                    flash(u'Der Anhang „%s“ wurde erfolgreich hinzugefügt'
                          % att_name, True)

        elif 'delete_attachment' in request.POST:
            id = int(request.POST['delete_attachment'])
            attachment = filter(lambda a: a.id==id, attachments)[0]
            attachment.delete()
            db.session.commit()
            attachments.remove(attachment)
            att_ids.remove(attachment.id)
            flash(u'Der Anhang „%s“ wurde gelöscht.' % attachment.name)

    # the user submitted a valid form
    if 'send' in request.POST and form.is_valid():
        d = form.cleaned_data

        if not post: # not when editing an existing post
            doublepost = Post.query \
                .filter_by(author_id=request.user.id, text=d['text']) \
                .filter(Post.pub_date > (datetime.utcnow() - timedelta(0, 120)))
            if not newtopic:
                doublepost = doublepost.filter_by(topic_id=topic.id)
            doublepost = doublepost.options(eagerload(Post.topic)).first()
            if doublepost:
                flash(u'Dieser Beitrag wurde bereits erstellt!  '
                      u'Bitte überlege ob du nicht deinen vorherigen Beitrag '
                      u'editieren möchtest.')
                return HttpResponseRedirect(url_for(doublepost.topic))

        if not topic:
            topic = Topic(forum_id=forum.id, author_id=request.user.id)
        if newtopic or firstpost:
            topic.title = d['title']
            if topic.ubuntu_distro != d.get('ubuntu_distro')\
               or topic.ubuntu_version != d.get('ubuntu_version'):
                topic.ubuntu_distro = d.get('ubuntu_distro')
                topic.ubuntu_version = d.get('ubuntu_version')
            if check_privilege(privileges, 'sticky'):
                topic.sticky = d['sticky']
            if check_privilege(privileges, 'create_poll'):
                topic.polls = polls
                topic.has_poll = bool(polls)
            db.session.commit()

            topic.forum.invalidate_topic_cache()
            topic.reindex()

        if not post:
            post = Post(topic=topic, author_id=request.user.id)
            if newtopic:
                post.position = 0
        post.edit(request, d['text'], d['is_plaintext'])
        db.session.commit()

        if attachments:
            Attachment.update_post_ids(att_ids, post.id)
        db.session.commit()

        if newtopic:
            notified_user = []
            for s in Subscription.objects.filter(forum_id=forum.id) \
                                         .exclude(user=request.user):
                notified_user.append(s.user)
                notify_about_subscription(s, 'new_topic',
                    u'Neues Thema im Forum %s: „%s“' % \
                        (forum.name, topic.title),
                    {'username':   s.user.username,
                     'post':       post,
                     'topic':      topic,
                     'forum':      forum})

            #Inform about ubuntu_version, without the users, which has already
            #imformed about this new topic
            for s in Subscription.objects.filter(ubuntu_version= \
                           topic.ubuntu_version) \
                           .exclude(user=request.user):
                if not s.user in notified_user:
                    notify_about_subscription(s, 'new_topic_ubuntu_version',
                        u'Neues Thema mit der Version %s: „%s“' % \
                            (topic.get_ubuntu_version(), topic.title),
                        {'username':   s.user.username,
                         'post':       post,
                         'topic':      topic,
                         'forum':      forum})

            # we always notify about new topics, even if the forum was
            # not visited, because unlike the posts you won't see
            # other new topics
        elif not post_id:
            for s in Subscription.objects.filter(topic_id=topic.id,
                                                 notified=False) \
                                         .exclude(user=request.user):
                notify_about_subscription(s, 'new_post',
                    u'Neue Antwort im Thema „%s“' % topic.title,
                    {'username':   s.user.username,
                     'post':       post,
                     'topic':      topic})
                s.notified = True
                s.save()

        if article:
            # the topic is a wiki discussion, bind it to the wiki
            # article and send notifications.
            article.topic_id = topic.id
            article.save()
            for s in Subscription.objects.filter(wiki_page=article) \
                                         .exclude(user=request.user):
                # also notify if the user has not yet visited the page,
                # since otherwise he would never know about the topic
                notify_about_subscription(s, 'new_page_discussion',
                    u'Neue Diskussion für die Seite „%s“ wurde eröffnet'
                    % article.title, {
                        'username': s.user.username,
                        'creator':  request.user.username,
                        'page':     article,
                    })
                s.notified = True
                s.save()

        if request.user.settings.get('autosubscribe', True) and \
           not Subscription.objects.user_subscribed(request.user,
                                                    topic=topic) \
           and not post_id:
            subscription = Subscription(
                user=request.user,
                topic_id=topic.id,
            )
            subscription.save()

        flash(u'Der Beitrag wurde erfolgreich gespeichert.', True)
        if post_id:
            flash(u'Es kann einige Minuten dauern, bis der Beitrag '
                  u'aktualisiert angezeigt wird.')
        if newtopic:
            return HttpResponseRedirect(url_for(post.topic))
        else:
            return HttpResponseRedirect(url_for(post))

    # the user wants to see a preview
    elif 'preview' in request.POST:
        ctx = RenderContext(request)
        tt = request.POST.get('text', '')
        preview = request.POST.get('is_plaintext', False) and \
            fix_plaintext(tt) or parse(tt).render(ctx, 'html')

    # the user is going to edit an existing post/topic
    elif post:
        form = form.__class__({
            'title': topic.title,
            'ubuntu_distro': topic.ubuntu_distro,
            'ubuntu_version': topic.ubuntu_version,
            'sticky': topic.sticky,
            'text': post.text,
            'is_plaintext': post.is_plaintext,
        })
        if not attachments:
            attachments = Attachment.query.filter_by(post_id=post.id)

    if not newtopic:
        posts = list(topic.posts.options(eagerload('author')) \
                                .filter(Post.hidden == False) \
                                .order_by(Post.position.desc())[:15])
        discussions = Page.objects.filter(topic_id=topic.id)

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
        'isfirstpost':  firstpost,
        'can_attach':   check_privilege(privileges, 'upload'),
        'can_create_poll':     check_privilege(privileges, 'create_poll'),
        'can_moderate': check_privilege(privileges, 'moderate'),
        'can_sticky':   check_privilege(privileges, 'sticky'),
        'attach_form':  attach_form,
        'attachments':  list(attachments),
        'posts':        posts,
        'storage':      storage,
        'discussions':  discussions,
    }


@simple_check_login
def change_status(request, topic_slug, solved=None, locked=None):
    """Change the status of a topic and redirect to it"""
    topic = Topic.query.filter_by(slug=topic_slug).first()
    if not topic:
        raise PageNotFound
    if not have_privilege(request.user, topic.forum, CAN_READ):
        abort_access_denied(request)
    if solved is not None:
        topic.solved = solved
        topic.reindex()
        db.session.commit()
        flash(u'Das Thema wurde als %s markiert' % (solved and u'gelöst' or \
                                                    u'ungelöst'), True)
    if locked is not None:
        topic.locked = locked
        db.session.commit()
        flash(u'Das Thema wurde %s' % (locked and u'gesperrt' or
                                       u'entsperrt'))
    topic.forum.invalidate_topic_cache()

    return HttpResponseRedirect(url_for(topic))


@transaction.autocommit
def _generate_subscriber(cls, obj_slug, subscriptionkw, flasher):
    """
    Generates a subscriber-function to deal with objects of type `obj`
    which have the slug `slug` and are registered in the subscription by
    `subscriptionkw` and have the flashing-test `flasher`
    """
    if subscriptionkw in ('forum', 'topic'):
        subscriptionkw = subscriptionkw + '_id'

    @simple_check_login
    def subscriber(request, **kwargs):
        """
        If the user has already subscribed to this %s, it just redirects.
        If there isn't such a subscription, a new one is created.
        """ % obj_slug
        slug = kwargs[obj_slug]
        obj = cls.query.filter(cls.slug==slug).one()
        if not have_privilege(request.user, obj, CAN_READ):
            return abort_access_denied(request)
        try:
            s = Subscription.objects.get(user=request.user, **{subscriptionkw: obj.id})
        except Subscription.DoesNotExist:
            # there's no such subscription yet, create a new one
            Subscription(user=request.user,**{subscriptionkw : obj.id}).save()
            flash(flasher)
        # redirect the user to the page he last watched
        if request.GET.get('continue', False) and is_safe_domain(request.GET['continue']):
            return HttpResponseRedirect(request.GET['continue'])
        else:
            return HttpResponseRedirect(url_for(obj))
    return subscriber


@transaction.autocommit
def _generate_unsubscriber(cls, obj_slug, subscriptionkw, flasher):
    """
    Generates an unsubscriber-function to deal with objects of type `obj`
    which have the slug `slug` and are registered in the subscription by
    `subscriptionkw` and have the flashing-test `flasher`
    """
    if subscriptionkw in ('forum', 'topic'):
        subscriptionkw = subscriptionkw + '_id'
    @simple_check_login
    def unsubscriber(request, **kwargs):
        """ If the user has already subscribed to this %s, this view removes it.
        """ % obj_slug
        slug = kwargs[obj_slug]
        obj = cls.query.filter(cls.slug==slug).one()
        try:
            s = Subscription.objects.get(user=request.user, **{subscriptionkw : obj.id})
        except Subscription.DoesNotExist:
            pass
        else:
            # there's already a subscription for this forum, remove it
            s.delete()
            flash(flasher)
        # redirect the user to the page he last watched
        if request.GET.get('continue', False) and is_safe_domain(request.GET['continue']):
            return HttpResponseRedirect(request.GET['continue'])
        else:
            return HttpResponseRedirect(url_for(obj))
    return unsubscriber

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
    topic = Topic.query.filter_by(slug=topic_slug).first()
    if not topic:
        raise PageNotFound()
    if not have_privilege(request.user, topic.forum, CAN_READ):
        return abort_access_denied(request)
    if topic.reported:
        flash(u'Dieses Thema wurde bereits gemeldet; die Moderatoren werden '
              u'sich in Kürze darum kümmern.')
        return HttpResponseRedirect(url_for(topic))

    if request.method == 'POST':
        form = ReportTopicForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            topic.reported = data['text']
            topic.reporter_id = request.user.id
            db.session.commit()

            users = (User.objects.get(id=int(i)) for i in
                    storage['reported_topics_subscribers'].split(',') if i)
            for user in users:
                send_notification(user, 'new_reported_topic',
                                  u'Thema gemeldet: %s' % topic.title,
                                  {'topic': topic, 'text':data['text']})

            cache.delete('forum/reported_topic_count')
            flash(u'Dieses Thema wurde den Moderatoren gemeldet. '
                  u'Sie werden sich sobald wie möglich darum kümmern.', True)
            return HttpResponseRedirect(url_for(topic))
    else:
        form = ReportTopicForm()
    return {
        'topic': topic,
        'form':  form
    }


@require_permission('manage_topics')
@templated('forum/reportlist.html')
def reportlist(request):
    """Get a list of all reported topics"""
    def _add_field_choices():
        """Add dynamic field choices to the reported topic formular"""
        form.fields['selected'].choices = [(t.id, u'') for t in topics]

    if 'assign' in request.GET and 'topic' in request.GET:
        topic = Topic.query.filter(Topic.slug == request.GET['topic']).one()
        topic.report_claimed_by_id = request.user.id
        db.session.commit()
        return HttpResponseRedirect(href('forum', 'reported_topics'))


    topics = Topic.query.filter(Topic.reported != None).all()
    if request.method == 'POST':
        form = ReportListForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            d = form.cleaned_data
            if not d['selected']:
                flash(u'Du hast keine Themen ausgewählt', False)
            else:
                db.session.execute(Topic.__table__.update(
                    Topic.id.in_(d['selected']), values={
                        'reported': None,
                        'reporter_id': None,
                        'report_claimed_by_id': None
                }))
                db.session.commit()
                cache.delete('forum/reported_topic_count')
                topics = filter(lambda t: str(t.id) not in d['selected'], topics)
                flash(u'Die gewählten Themen wurden als bearbeitet markiert.',
                      True)
    else:
        form = ReportListForm()
        _add_field_choices()

    subscribed = str(request.user.id) in \
            storage['reported_topics_subscribers'].split(',')

    return {
        'topics':     topics,
        'form':       form,
        'subscribed': subscribed,
    }

def reported_topics_subscription(request, mode):
    users = set(int(i) for i in storage['reported_topics_subscribers'].split(',') if i)

    if mode == 'subscribe':
        if not request.user.can('manage_topics'):
            flash(u'Keine Rechte!', False)
            return HttpResponseRedirect(href('forum'))
        users.add(request.user.id)
        flash(u'Du wirst ab sofort benachrichtigt, wenn ein Thema gemeldet wird.', True)
    elif mode == 'unsubscribe':
        try:
            users.remove(request.user.id)
        except KeyError:
            pass
        flash(u'Du wirst nicht mehr benachrichtigt, wenn ein Thema gemeldet wird.', True)

    storage['reported_topics_subscribers'] = ','.join(str(i) for i in users)

    return HttpResponseRedirect(href('forum', 'reported_topics'))


def post(request, post_id):
    """Redirect to the "real" post url" (see `PostManager.url_for_post`)"""
    url = Post.url_for_post(int(post_id),
        paramstr=request.GET and request.GET.urlencode())
    if not url:
        raise PageNotFound()
    return HttpResponseRedirect(url)


def first_unread_post(request, topic_slug):
    """
    Redirect the user to the first unread post in a special topic.
    """
    topic_id, forum_id = db.session.query(Topic.id, Topic.forum_id) \
                                   .filter(Topic.slug==topic_slug).first()
    if not topic_id or not forum_id:
        # there's no topic with such a slug
        raise PageNotFound()

    data = request.user._readstatus.data.get(forum_id, [None, []])
    query = db.session.query(Post.id).filter(Post.topic_id == topic_id)

    last_pid, ids = data
    if last_pid is not None:
        query = query.filter(Post.id > last_pid)

    if ids:
        # We need a try/catch here, cause the post don't have to exist
        # any longer.
        try:
            post_id = max(p.id for p in db.session.query(Post.id) \
                .filter(db.and_(Post.topic_id == topic_id,
                                Post.id.in_(ids))).all())
        except ValueError:
            pass
        else:
            query = query.filter(Post.id > post_id)

    first_unread_post = query.order_by(Post.id).limit(1).first()
    if first_unread_post is not None:
        redirect = Post.url_for_post(first_unread_post.id)
    else:
        # No new post, this also means the user called first_unread himself
        # as the icon won't show up in that case, hence we just return to
        # page one of the topic.
        redirect = href('forum', 'topic', topic_slug)
    return HttpResponseRedirect(redirect)


@templated('forum/movetopic.html')
def movetopic(request, topic_slug):
    """Move a topic into another forum"""
    def _add_field_choices():
        """Add dynamic field choices to the move topic formular"""
        forums = Forum.get_children_recursive(Forum.query.get_cached())
        form.fields['forum_id'].choices = (
            (f.id, f.name[0] + u' ' + (u'   ' * offset) + f.name)
            for offset, f in forums)
        #TODO: add disabled="disabled" to categories and current forum
        #      (django doesn't feature that atm)

    topic = Topic.query.filter_by(slug=topic_slug).first()
    if not topic:
        raise PageNotFound
    if not have_privilege(request.user, topic.forum, CAN_MODERATE):
        return abort_access_denied(request)

    forums = filter_invisible(request.user,
        [forum for forum in Forum.query.get_cached() if
            forum.parent_id != None and forum.id != topic.forum_id])
    mapping = dict((x.id, x) for x in forums)
    if not mapping:
        return abort_access_denied(request)

    if request.method == 'POST':
        form = MoveTopicForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            data = form.cleaned_data
            forum = mapping.get(int(data['forum_id']))
            if forum is None:
                return abort_access_denied(request)
            topic.move(forum)
            db.session.commit()
            # send a notification to the topic author to inform him about
            # the new forum.
            nargs = {
                'username':   topic.author.username,
                'topic':      topic,
                'mod':        request.user.username,
                'forum_name': forum.name
            }
            if 'topic_move' in\
            topic.author.settings.get('notifications',('topic_move',))\
            and topic.author.username != request.user.username:
                send_notification(topic.author, 'topic_moved',
                    u'Dein Thema „%s“ wurde verschoben'
                    % topic.title, nargs)

            users_done = set([topic.author.id,request.user.id])
            subscriptions = Subscription.objects.filter(Q(topic_id=topic.id) | Q(forum_id=forum.id))
            for subscription in subscriptions:
                if subscription.user.id in users_done:
                    continue
                nargs['username'] = subscription.user.username
                notify_about_subscription(subscription, 'topic_moved',
                    u'Das Thema „%s“ wurde verschoben' % topic.title, nargs)
                users_done.add(subscription.user.id)
            return HttpResponseRedirect(url_for(topic))
    else:
        form = MoveTopicForm()
        _add_field_choices()
    return {
        'form':  form,
        'topic': topic
    }


@templated('forum/splittopic.html')
def splittopic(request, topic_slug, page=1):
    def _add_field_choices():
        """Add dynamic field choices to the move topic formular"""
        forums = Forum.get_children_recursive(Forum.query.get_cached())
        form.fields['forum'].choices = (
            (f.id, f.name[0] + u' ' + (u'   ' * offset) + f.name)
            for offset, f in forums)
        form.fields['start'].choices = form.fields['select'].choices = \
            [(p.id, u'') for p in old_posts]

    old_topic = Topic.query.filter_by(slug=topic_slug).first()

    if not old_topic:
        raise PageNotFound

    if not have_privilege(request.user, old_topic.forum, CAN_MODERATE):
        return abort_access_denied(request)

    pagination = Pagination(request, old_topic.posts, page, POSTS_PER_PAGE,
        url_for(old_topic, action='split'), total=old_topic.post_count,
        rownum_column=Post.position)

    old_posts = old_topic.posts

    if request.method == 'POST' and ('switch1' in request.POST or
                                     'switch2' in request.POST):
        form = SplitTopicForm(data=request.POST)
        _add_field_choices()
        form._errors = ErrorDict()
        if 'switch1' in request.POST:
            switch_to = int(request.POST['switch_to1'])
        if 'switch2' in request.POST:
            switch_to = int(request.POST['switch_to2'])

        pagination = Pagination(request, old_topic.posts, switch_to, POSTS_PER_PAGE,
            url_for(old_topic, action='split'), total=old_topic.post_count,
            rownum_column=Post.position)

        rendered_posts = pagination.objects.all()

        return {
            'topic': old_topic,
            'forum': old_topic.forum,
            'form':  form,
            'pagination': pagination.generate(),
            'posts': rendered_posts,
            'current_page': switch_to,
            'max_pages': pagination.max_pages,
            'post_ids': [p.id for p in rendered_posts],
            'selected_ids': [int(id) for id in request.POST.getlist('select')],
            'selected_start': int(request.POST.get('start') or 0)
        }

    elif request.method == 'POST':
        form = SplitTopicForm(request.POST)
        _add_field_choices()

        if form.is_valid():
            data = form.cleaned_data

            if data['select_following']:
                posts = old_posts.filter(Post.id >= data['start'])
            else:
                posts = old_posts.filter(Post.id.in_(data['select']))

            posts = list(posts)

            try:
                if data['action'] == 'new':
                    new_topic = Topic(
                        title=data['title'],
                        forum=data['forum'],
                        slug=None,
                        post_count=0,
                        author_id=posts[0].author_id,
                        ubuntu_version=data['ubuntu_version'],
                        ubuntu_distro=data['ubuntu_distro'],
                    )
                    db.atomic_add(new_topic.forum, 'topic_count', 1)
                    db.session.commit()
                    Post.split(posts, old_topic, new_topic)
                else:
                    new_topic = data['topic']
                    Post.split(posts, old_topic, new_topic)

                db.session.commit()
            except ValueError:
                db.session.rollback()
                flash(u'Du kannst ein Topic nicht in eine Kategorie verschieben. '
                      u'Bitte wähle ein richtiges Forum aus.', False)
                return {
                    'topic': old_topic,
                    'forum': old_topic.forum,
                    'form':  form,
                    'pagination': pagination.generate(),
                    'posts': pagination.objects.all(),
                    'current_page': page,
                    'max_pages': pagination.max_pages,
                    'selected_ids': [int(id) for id in request.POST.getlist('select')],
                    'selected_start': int(request.POST.get('start') or 0)
                }

            new_forum = new_topic.forum
            nargs = {
                'username': None,
                'new_topic': new_topic,
                'old_topic': old_topic,
                'mod': request.user.username
            }
            users_done = set([request.user.id])
            filter = Q(topic_id=old_topic.id)
            if data['action'] == 'new':
                filter |= Q(forum_id=new_forum.id)
            #TODO: Disable until http://forum.ubuntuusers.de/topic/benachrichtigungen-nach-teilung-einer-diskuss/ is resolved to not spam the users
            #subscriptions = Subscription.objects.select_related('user').filter(filter)
            subscriptions = []

            for subscription in subscriptions:
                # Skip loop for users already notified:
                if subscription.user.id in users_done:
                    continue
                # Added Users to users_done which should not get any
                # notification for splited Topics:
                if 'topic_split' not in subscription.user.settings.get('notifications',('topic_split',)):
                    users_done.add(subscription.user.id)
                    continue
                nargs['username'] = subscription.user.username
                notify_about_subscription(subscription, 'topic_splited',
                    u'Das Thema „%s“ wurde aufgeteilt.' % old_topic.title, nargs)
                users_done.add(subscription.user.id)
            return HttpResponseRedirect(url_for(new_topic))
    else:
        form = SplitTopicForm(initial={
            'forum': old_topic.forum_id,
            'ubuntu_version': old_topic.ubuntu_version,
            'ubuntu_distro': old_topic.ubuntu_distro,
        })
        _add_field_choices()

    return {
        'topic': old_topic,
        'forum': old_topic.forum,
        'form':  form,
        'pagination': pagination.generate(),
        'posts': pagination.objects.all(),
        'current_page': page,
        'max_pages': pagination.max_pages
    }


def restore_post(request, post_id):
    """
    This function removes the hidden flag of a post to make it visible for
    normal users again.
    """
    post = Post.query.get(post_id)
    if not post:
        raise PageNotFound
    if not have_privilege(request.user, post.topic.forum, CAN_MODERATE):
        return abort_access_denied(request)
    post.hidden = False
    db.session.commit()
    flash(u'Der Beitrag von „<a href="%s">%s</a>“ wurde wieder sichtbar '
          u'gemacht.' % (url_for(post), escape(post.author.username)),
          success=True)
    return HttpResponseRedirect(url_for(post).split('#')[0])


def delete_post(request, post_id, action='hide'):
    """
    Sets the hidden flag of a post to True if action == 'hide'. which has the
    effect that normal users can't see it anymore (moderators still can). If
    action == 'delete' really deletes the post.
    """
    post = Post.query.get(post_id)
    if not post:
        raise PageNotFound

    if not have_privilege(request.user, post.topic.forum, CAN_MODERATE) and not\
       (post.author_id==request.user.id and post.check_ownpost_limit('delete')):
        flash(u'Du darfst diesen Beitrag nicht löschen!', False)
        return HttpResponseRedirect(href('forum', 'topic', post.topic.slug,
                                         post.page))

    if post.id == post.topic.first_post.id:
        if post.topic.post_count == 1:
            return HttpResponseRedirect(href('forum', 'topic',
                                             post.topic.slug, action))
        t = u'gelöscht' if action=='delete' else u'unsichtbar gemacht'
        flash(u'Der erste Beitrag eines Themas darf nicht %s werden' % t,
              success=False)
    else:
        if request.method == 'POST':
            if 'cancel' in request.POST:
                t = u'Löschen' if action == u'delete' else u'Verbergen'
                flash(u'Das %s wurde abgebrochen.' % t)
            else:
                if action == 'hide':
                    post.hidden = True
                    flash(u'Der Beitrag von „<a href="%s">%s</a>“ wurde unsichtbar '
                          u'gemacht.' % (url_for(post), escape(post.author.username)),
                          success=True)
                    db.session.commit()
                    return HttpResponseRedirect(url_for(post))
                elif action == 'delete':
                    author = post.author
                    db.session.delete(post)
                    db.session.commit()
                    last_post = Post.query.filter_by(topic_id=post.topic_id) \
                                          .order_by('-id').first()
                    post.topic.last_post_id = last_post.id
                    flash(u'Der Beitrag von <a href="%s">%s</a> wurde gelöscht.'
                          % (url_for(author), escape(author.username)),
                          success=True)
                    db.session.commit()
        else:
            flash(render_template('forum/post_delete.html',
                                  {'post': post, 'action': action}))

    return HttpResponseRedirect(href('forum', 'topic', post.topic.slug,
                                     post.page))



@templated('forum/revisions.html')
def revisions(request, post_id):
    post = Post.query.options(eagerload('topic'), eagerload('topic.forum')) \
                  .get(post_id)
    topic = post.topic
    forum = topic.forum
    if not have_privilege(request.user, forum, CAN_MODERATE):
        return abort_access_denied(request)
    revs = list(PostRevision.query.filter(PostRevision.post_id == post_id))
    return {
        'post':      post,
        'topic':     topic,
        'forum':     forum,
        'revisions': reversed(revs)
    }


def restore_revision(request, rev_id):
    rev = PostRevision.query.options(eagerload('post'),
        eagerload('post.topic'), eagerload('post.topic.forum')).get(rev_id)
    if not have_privilege(request.user, rev.post.topic.forum, CAN_MODERATE):
        return abort_access_denied(request)
    rev.restore(request)
    db.session.commit()
    flash(u'Eine alte Version des Beitrags wurde wiederhergestellt.', True)
    return HttpResponseRedirect(href('forum', 'post', rev.post_id))


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
    db.session.commit()
    flash(u'Das Thema „%s“ wurde wieder sichtbar gemacht.' % topic.title,
          success=True)
    topic.forum.invalidate_topic_cache()
    return HttpResponseRedirect(url_for(topic))


def delete_topic(request, topic_slug, action='hide'):
    """
    Sets the hidden flag of a topic to True if action=='hide', which has the
    effect that normal users can't see it anymore (moderators still can).
    Completely deletes the topic if action=='delete'.
    """
    topic = Topic.query.filter_by(slug=topic_slug).first()
    if not topic:
        raise PageNotFound
    if not request.user.can('delete_topic') or not have_privilege(
            request.user, topic.forum, CAN_MODERATE):
        return abort_access_denied(request)

    if request.method == 'POST':
        if 'cancel' in request.POST:
            flash(u'Löschen des Themas „%s“ wurde abgebrochen' % topic.title)
        else:
            if action == 'hide':
                redirect = url_for(topic)
                topic.hidden = True
                flash(u'Das Thema „%s“ wurde unsichtbar gemacht.' % topic.title,
                      success=True)

            elif action == 'delete':
                redirect = url_for(topic.forum)
                subscriptions = Subscription.objects.filter(topic_id=topic.id)
                sids = [s.id for s in subscriptions]
                for subscription in subscriptions:
                    nargs = {
                        'username' : subscription.user.username,
                        'mod'      : request.user.username,
                        'topic'    : topic,
                        'reason'   : request.POST.get('reason', None),
                    }
                    notify_about_subscription(subscription, 'topic_deleted',
                        u'Das Thema „%s“ wurde gelöscht' % topic.title, nargs)
                db.session.delete(topic)
                flash(u'Das Thema „%s“ wurde erfolgreich gelöscht' % topic.title,
                      success=True)

            db.session.commit()
            topic.forum.invalidate_topic_cache()
            return HttpResponseRedirect(redirect)
    else:
        flash(render_template('forum/delete_topic.html', {'topic': topic, 'action': action}))

    return HttpResponseRedirect(url_for(topic))


@atom_feed()
def topic_feed(request, slug=None, mode='short', count=20):
    # We have one feed, so we use ANONYMOUS_USER to cache the correct feed.
    anonymous = User.objects.get_anonymous_user()

    topic = Topic.query.filter_by(slug=slug).first()

    if topic is None or topic.hidden:
        raise PageNotFound()
    # We check if request.user has CAN_READ, though we only display
    # the anonymous feed; this is to allow logged in users to view
    # the feeds (eg in firefox).
    if not have_privilege(request.user, topic.forum, CAN_READ):
        return abort_access_denied(request)

    posts = topic.posts.options(eagerload('author')) \
                       .order_by(Post.id.desc())[:100]

    feed = FeedBuilder(
        title=u'ubuntuusers Thema – „%s“' % topic.title,
        url=url_for(topic),
        feed_url=request.build_absolute_uri(),
        rights=href('portal', 'lizenz'),
        icon=href('static', 'img', 'favicon.ico'),
    )

    for post in posts:
        kwargs = {}
        if mode == 'full':
            kwargs['content'] = post.get_text()
            kwargs['content_type'] = 'xhtml'
        if mode == 'short':
            kwargs['summary'] = truncate_html_words(post.get_text(), 100)
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
    return feed


@atom_feed('forum/feeds/forum/%(slug)s/%(mode)s/%(count)s')
def forum_feed(request, slug=None, mode='short', count=20):
    # We have one feed, so we use ANONYMOUS_USER to cache the correct feed.
    anonymous = User.objects.get_anonymous_user()

    if slug:
        forum = Forum.query.get_cached(slug=slug)
        if forum is None:
            raise PageNotFound()
        # We check if request.user has CAN_READ, though we only display
        # the anonymous feed; this is to allow logged in users to view
        # the feeds (eg in firefox).
        if not have_privilege(request.user, forum, CAN_READ):
            return abort_access_denied(request)

        topics = forum.get_latest_topics(count=count)
        title = u'ubuntuusers Forum – „%s“' % forum.name
        url = url_for(forum)
    else:
        allowed_forums = [f.id for f in filter_invisible(anonymous, Forum.query.get_cached())]
        if not allowed_forums:
            return abort_access_denied(request)
        topics = Topic.query.order_by(Topic.id.desc()).options(
            eagerload('first_post'), eagerload('author')
        ).filter(Topic.forum_id.in_(allowed_forums))[:count]
        title = u'ubuntuusers Forum'
        url = href('forum')

    feed = FeedBuilder(
        title=title,
        url=url,
        feed_url=request.build_absolute_uri(),
        rights=href('portal', 'lizenz'),
        icon=href('static', 'img', 'favicon.ico'),
    )

    for topic in topics:
        kwargs = {}
        post = topic.first_post

        #XXX: this way there might be less than `count` items
        if topic.hidden or post is None:
            continue

        if post.rendered_text is None and not post.is_plaintext:
            post.render_text()
        text = post.get_text()

        if mode == 'full':
            kwargs['content'] = text
            kwargs['content_type'] = 'xhtml'
        if mode == 'short':
            kwargs['summary'] = truncate_html_words(text, 100)
            kwargs['summary_type'] = 'xhtml'

        feed.add(
            title=topic.title,
            url=url_for(topic),
            author={
                'name': topic.author.username,
                'uri': url_for(topic.author),
            },
            published=post.pub_date,
            updated=post.pub_date,
            **kwargs
        )

    return feed


@transaction.autocommit
def markread(request, slug=None):
    """
    Mark either all or only the given forum as read.
    """
    user = request.user
    if user.is_anonymous:
        flash(u'Bitte melde dich an, um Beiträge als gelesen zu markieren.')
        return HttpResponseRedirect(href('forum'))
    if slug:
        forum = Forum.query.filter_by(slug=slug).first()
        if not forum:
            raise PageNotFound()
        forum.mark_read(user)
        user.save()
        flash(u'Das Forum „%s“ wurde als gelesen markiert.' % forum.name,
              True)
        return HttpResponseRedirect(url_for(forum))
    else:
        for row in Forum.query.filter(Forum.parent_id == None):
            row.mark_read(user)
        user.save()
        flash(u'Alle Foren wurden als gelesen markiert.', True)
    return HttpResponseRedirect(href('forum'))


MAX_PAGES_TOPICLIST = 50

@templated('forum/topiclist.html')
def topiclist(request, page=1, action='newposts', hours=24, user=None):
    page = int(page)

    if action != 'author' and page > MAX_PAGES_TOPICLIST:
        flash(u'Du kannst maximal die letzten %s Seiten anzeigen lassen' % MAX_PAGES_TOPICLIST)
        return HttpResponseRedirect(href('forum'))

    topics = db.session.query(Topic.id).order_by(Topic.last_post_id.desc())

    if 'version' in request.GET:
        topics = topics.filter_by(ubuntu_version=request.GET['version'])

    if action == 'last':
        hours = int(hours)
        if hours > 24:
            raise PageNotFound()
        topics = topics.filter(and_(
            Topic.last_post_id == Post.id,
            Post.pub_date > datetime.utcnow() - timedelta(hours=hours)
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
    elif action == 'topic_author':
        user = User.objects.get(user)
        topics = topics.filter(Topic.author_id == user.id)
        url = href('forum', 'topic_author', user.username)
        title = u'Themen von %s' % (escape(user.username))
    elif action == 'author':
        user = user and User.objects.get(user) or request.user
        if user.is_anonymous:
            flash(u'Für diese Funktion musst du eingeloggt sein')
            return abort_access_denied(request)
        topics = topics.join((Post, db.and_(Post.author_id == user.id, Post.topic_id == Topic.id))).distinct()

        if user != request.user:
            title = u'Beiträge von %s' % escape(user.username)
            url = href('forum', 'author', user.username)
        else:
            title = u'Eigene Beiträge'
            url = href('forum', 'egosearch')
    elif action == 'newposts':
        forum_ids = tuple(forum.id for forum in Forum.query.get_cached())
        # get read status data
        read_status = request.user._readstatus.data
        read_topics = tuple(flatten_iterator(
            read_status.get(id, [None, []])[1] for id in forum_ids
        ))
        if read_topics:
            topics = topics.filter(db.not_(Topic.last_post_id.in_(read_topics)))
        url = href('forum', 'newposts')
        title = u'Neue Beiträge'

    invisible = [f.id for f in Forum.query.get_forums_filtered(request.user, reverse=True)]
    if invisible:
        topics = topics.filter(db.not_(Topic.forum_id.in_(invisible)))
    total_topics = topics.limit(TOPICS_PER_PAGE * MAX_PAGES_TOPICLIST).count()
    pagination = Pagination(request, topics, page, TOPICS_PER_PAGE, url,
                            total=total_topics)
    topic_ids = (obj.id for obj in pagination.objects)
    pagination = pagination.generate()

    def _get_read_status(post_id):
        user = request.user
        return user.is_authenticated and user._readstatus(post_id=post_id)

    # check for moderatation permissions
    moderatable_forums = [forum.id for forum in
        Forum.query.get_forums_filtered(request.user, CAN_MODERATE, reverse=True)
    ]
    def can_moderate(topic):
        return topic.forum_id not in moderatable_forums

    if topic_ids:
        topics = Topic.query.filter(Topic.id.in_(topic_ids)) \
                    .options(db.eagerload('forum'),
                             db.eagerload('author'),
                             db.eagerload_all('last_post.author'),
                             db.eagerload('first_post')).all()
        topics.sort(key=attrgetter('last_post_id'), reverse=True)
    else:
        topics = []

    return {
        'topics':       topics,
        'pagination':   pagination,
        'title':        title,
        'get_read_status':  _get_read_status,
        'can_moderate': can_moderate,
        'hide_sticky': False
    }


@templated('forum/welcome.html')
def welcome(request, slug, path=None):
    """
    Show a welcome message on the first visit to greet the users or
    inform him about special rules.
    """
    user = request.user
    forum = Forum.query.filter_by(slug=slug).first()
    if not forum.welcome_message_id:
        raise PageNotFound()
    goto_url = path or url_for(forum)
    if request.method == 'POST':
        accepted = request.POST.get('accept', False) and True
        forum.read_welcome(request.user, accepted)
        db.session.commit()
        if accepted:
            return HttpResponseRedirect(request.POST.get('goto_url'))
        else:
            return HttpResponseRedirect(href('forum'))
    return {
        'goto_url': goto_url,
        'message': WelcomeMessage.query.get(forum.welcome_message_id),
        'forum': forum
    }


def next_topic(request, topic_slug):
    this = Topic.query.filter_by(slug=topic_slug).first()
    if this is None:
        raise PageNotFound
    next = Topic.query.filter_by(forum_id=this.forum_id) \
                      .filter(Topic.last_post_id > this.last_post_id) \
                      .order_by('last_post_id').first()
    if next is None:
        flash('Es gibt keine neueren Themen in diesem Forum.')
        next = this.forum
    return HttpResponseRedirect(url_for(next))


def previous_topic(request, topic_slug):
    this = Topic.query.filter_by(slug=topic_slug).first()
    if this is None:
        raise PageNotFound
    previous = Topic.query.filter_by(forum_id=this.forum_id) \
                          .filter(Topic.last_post_id < this.last_post_id) \
                          .order_by('-last_post_id').first()
    if previous is None:
        flash('Es gibt keine neueren Themen in diesem Forum.')
        previous = this.forum
    return HttpResponseRedirect(url_for(previous))
