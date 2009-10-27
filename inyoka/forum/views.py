# -*- coding: utf-8 -*-
"""
    inyoka.forum.views
    ~~~~~~~~~~~~~~~~~~

    The views for the forum.

    :copyright: Copyright 2007-2008 by Benjamin Wiegand, Christopher Grebs,
                                       Christoph Hack.
    :license: GNU GPL.
"""
import re
from datetime import datetime, timedelta
from django.utils.text import truncate_html_words
from django.db import transaction
from django.db.models import Q
from sqlalchemy.orm import eagerload
from sqlalchemy.sql import and_, or_, select, not_, exists, func
from sqlalchemy.exceptions import InvalidRequestError, OperationalError
from inyoka.conf import settings
from inyoka.utils.urls import global_not_found, href, url_for, is_safe_domain
from inyoka.utils.html import escape
from inyoka.utils.text import normalize_pagename
from inyoka.utils.sessions import set_session_info
from inyoka.utils.http import templated, does_not_exist_is_404, \
    PageNotFound, HttpResponseRedirect
from inyoka.utils.feeds import FeedBuilder, atom_feed
from inyoka.utils.flashing import flash
from inyoka.utils.templating import render_template
from inyoka.utils.pagination import Pagination
from inyoka.utils.notification import send_notification, notify_about_subscription
from inyoka.utils.cache import cache
from inyoka.utils.dates import format_datetime
from inyoka.utils.database import session
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
    CACHE_PAGES_COUNT, WelcomeMessage, fix_plaintext
from inyoka.forum.forms import NewTopicForm, SplitTopicForm, EditPostForm, \
    AddPollForm, MoveTopicForm, ReportTopicForm, ReportListForm, \
    AddAttachmentForm
from inyoka.forum.acl import filter_invisible, get_forum_privileges, \
    have_privilege, get_privileges, CAN_READ, CAN_MODERATE, \
    check_privilege, DISALLOW_ALL
from inyoka.forum.database import post_table, topic_table, forum_table, \
    poll_option_table, attachment_table, privilege_table

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
    if category:
        key = 'forum/category/%s' % category
        session_info = ((u'sieht sich die Forenübersicht der '
                            u'Kategorie „%s“ an' % category),
                        u'Kategorieübersicht')
    else:
        key = 'forum/index'
        session_info = (u'sieht sich die Forenübersicht an.',
                        u'Forenübersicht')

    categories = cache.get(key)
    if categories is None:
        query = Forum.query.options(eagerload('_children'),
                                    eagerload('_children.last_post'),
                                    eagerload('_children.last_post.author'))
        if category:
            category = query.get(category)
            if not category or category.parent_id != None:
                raise PageNotFound

            if have_privilege(User.ANONYMOUS_USER, category, 'read'):
                set_session_info(request, session_info)
            categories = [category]

            fmsg = category.find_welcome(request.user)
            if fmsg is not None:
                return welcome(request, fmsg.slug, request.path)
        else:
            categories = list(query.filter(forum_table.c.parent_id == None) \
                              .order_by(forum_table.c.position))
            # forum-overview can be set without any acl check ;)
            set_session_info(request, session_info)

        cache.set(key, categories, 120)

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
    key = 'forum/forum/%s' % slug
    f = cache.get(key)

    if f is None:
        f = Forum.query.options(eagerload('_children'),
                                eagerload('_children.last_post'),
                                eagerload('_children.last_post.author')) \
                .get(slug)

        # if the forum is a category we raise PageNotFound. Categories have
        # their own url at /category.
        if not f or f.parent_id is None:
            raise PageNotFound()

        cache.set(key, f, 60)

    privs = get_forum_privileges(request.user, f.id)
    if not check_privilege(privs, 'read'):
        return abort_access_denied(request)

    fmsg = f.find_welcome(request.user)
    if fmsg is not None:
        return welcome(request, fmsg.slug, request.path)

    if page < CACHE_PAGES_COUNT:
        key = 'forum/topics/%d/%d' % (f.id, int(page))
        ctx = cache.get(key)
    else:
        ctx = None

    if ctx is None:
        topics = Topic.query.options(eagerload('author'),
                                     eagerload('last_post'),
                                     eagerload('last_post.author')) \
            .filter_by(forum_id=f.id) \
            .order_by((topic_table.c.sticky.desc(),
                       topic_table.c.last_post_id.desc()))

        pagination = Pagination(request, topics, page, TOPICS_PER_PAGE, url_for(f))

        ctx = {
            'topics':           list(pagination.objects),
            'pagination_left':  pagination.generate(),
            'pagination_right': pagination.generate('right')
        }

        if page < CACHE_PAGES_COUNT:
            cache.set(key, ctx, 60)

    if have_privilege(User.ANONYMOUS_USER, f, 'read'):
        set_session_info(request, u'sieht sich das Forum „<a href="%s">'
                         u'%s</a>“ an' % (escape(url_for(f)), escape(f.name)),
                         'besuche das Forum')

    supporters = cache.get('forum/forum/supporters-%s' % f.id)
    if supporters is None:
        p = privilege_table.c
        supporters = []
        cur = session.execute(select([p.user_id, p.positive],
            (p.forum_id == f.id) &
            (p.user_id != None)
        )).fetchall()
        subset = [r.user_id for r in cur if check_privilege(r.positive, 'moderate')]
        if subset:
            supporters = User.objects.filter(id__in=subset).order_by('username').all()
        cache.set('forum/forum/supporters-%s' % f.id, supporters, 600)

    ctx.update({
        'forum':         f,
        'subforums':     filter_invisible(request.user, f._children),
        'is_subscribed': Subscription.objects.user_subscribed(request.user,
                                                              forum=f),
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
    t = Topic.query.filter_by(slug=topic_slug).first()
    if not t:
        raise PageNotFound('no such topic')
    privileges = get_forum_privileges(request.user, t.forum.id)
    if not check_privilege(privileges, 'read'):
        return abort_access_denied(request)
    if t.hidden:
        if not check_privilege(privileges, 'moderate'):
            flash(u'Dieses Thema wurde von einem Moderator gelöscht.')
            return HttpResponseRedirect(url_for(t.forum))
        flash(u'Dieses Thema ist unsichtbar für normale Benutzer.')
    fmsg = t.forum.find_welcome(request.user)
    if fmsg is not None:
        return welcome(request, fmsg.slug, request.path)
    try:
        t.touch()
        session.commit()
    except OperationalError:
        pass

    discussions = Page.objects.filter(topic_id=t.id)

    posts = t.posts.options(eagerload('author'), eagerload('attachments')) \
                   .order_by(post_table.c.position)

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
                     total=t.post_count, rownum_column=post_table.c.position)

    if have_privilege(User.ANONYMOUS_USER, t, 'read'):
        set_session_info(request, u'sieht sich das Thema „<a href="%s">%s'
            u'</a>“ an' % (url_for(t), escape(t.title)), 'besuche Thema')

    subscribed = False
    if request.user.is_authenticated:
        t.mark_read(request.user)
        request.user.save()

        s = Subscription.objects.filter(user=request.user,
                                        topic_id=t.id)
        if s:
            subscribed = True
            s[0].notified = False
            s[0].save()
        else:
            subscribed = False

    post_objects = pagination.objects.all()

    for post in post_objects:
        if not post.rendered_text and not post.is_plaintext:
            try:
                post.rendered_text = post.render_text(force_existing=True)
                session.commit()
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
        'forum':             t.forum,
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
        forum = Forum.query.get(forum_slug)
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
            session.commit()
            if topic:
                topic.has_poll = True
                session.commit()
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
                    session.commit()
                    attachments.append(attachment)
                    att_ids.append(attachment.id)
                    flash(u'Der Anhang „%s“ wurde erfolgreich hinzugefügt'
                          % att_name, True)

        elif 'delete_attachment' in request.POST:
            id = int(request.POST['delete_attachment'])
            attachment = filter(lambda a: a.id==id, attachments)[0]
            attachment.delete()
            session.commit()
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
                topic.reindex()
            if check_privilege(privileges, 'sticky'):
                topic.sticky = d['sticky']
            if check_privilege(privileges, 'create_poll'):
                topic.polls = polls
                topic.has_poll = bool(polls)
            session.commit()

            topic.forum.invalidate_topic_cache()

        if not post:
            post = Post(topic=topic, author_id=request.user.id)
            if newtopic:
                post.position = 0
        post.edit(request, d['text'], d['is_plaintext'])
        session.commit()

        if attachments:
            Attachment.update_post_ids(att_ids, post.id)
        session.commit()

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
                                                    topic=topic):
            subscription = Subscription(
                user=request.user,
                topic_id=topic.id,
            )
            subscription.save()

        flash(u'Der Beitrag wurde erfolgreich gespeichert', True)
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
        posts = list(topic.posts.filter(post_table.c.hidden == 0) \
                                .order_by(post_table.c.position.desc())[:15])
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
        'discussions':  discussions
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
        session.commit()
        flash(u'Das Thema wurde als %s markiert' % (solved and u'gelöst' or \
                                                    u'ungelöst'), True)
    if locked is not None:
        topic.locked = locked
        session.commit()
        flash(u'Das Thema wurde %s' % (locked and u'gesperrt' or
                                       u'entsperrt'))
    topic.forum.invalidate_topic_cache()

    return HttpResponseRedirect(url_for(topic))


@transaction.autocommit
def _generate_subscriber(obj, obj_slug, subscriptionkw, flasher):
    """
    Generates a subscriber-function to deal with objects of type `obj`
    which have the slug `slug` and are registered in the subscription by
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
        # redirect the user to the page he last watched
        if request.GET.get('continue', False) and is_safe_domain(request.GET['continue']):
            return HttpResponseRedirect(request.GET['continue'])
        else:
            return HttpResponseRedirect(url_for(x))
    return subscriber


@transaction.autocommit
def _generate_unsubscriber(obj, obj_slug, subscriptionkw, flasher):
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
        x = obj.query.filter(obj.slug==slug).one()
        try:
            s = Subscription.objects.get(user=request.user, **{subscriptionkw : x.id})
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
            return HttpResponseRedirect(url_for(x))
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
            session.commit()

            users = (User.objects.get(id=int(i)) for i in
                    storage['reported_topics_subscribers'].split(',') if i)
            for user in users:
                send_notification(user, 'new_reported_topic',
                                  u'Thema gemeldet: %s' % topic.title,
                                  {'topic': topic})

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
        session.commit()
        return HttpResponseRedirect(href('forum', 'reported_topics'))

    topics = Topic.query.filter(Topic.reported != None)
    if request.method == 'POST':
        form = ReportListForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            d = form.cleaned_data
            session.execute(topic_table.update(
                topic_table.c.id.in_(d['selected']), values={
                    'reported': None,
                    'reporter_id': None,
                    'report_claimed_by_id': None
            }))
            session.commit()
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
        'topics':     list(topics),
        'form':       form,
        'subscribed': subscribed,
    }

def reported_topics_subscription(request, mode):
    users = set(int(i) for i in storage['reported_topics_subscribers'].split(',') if i)

    if mode == 'subscribe':
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
    t = topic_table.c
    p = post_table.c
    try:
        topic_id, forum_id = select([t.id, t.forum_id],
            t.slug == topic_slug).execute().fetchone()
    except TypeError:
        # there's no topic with such a slug
        raise PageNotFound()

    data = request.user._readstatus.data.get(forum_id, [None, []])
    query = select([p.id], p.topic_id == topic_id)

    if data[0] is not None:
        query = query.where(p.id > data[0])

    if data[1]:
        try:
            #: the id of the latest read post in this topic
            post_id = max(p[0] for p in select([p.id],
                    (p.topic_id == topic_id) &
                    (p.id.in_(data[1]))
                ).execute().fetchall()
            )
        except ValueError:
            pass
        else:
            query = query.where(p.id > post_id)

    try:
        post_id = query.order_by(p.id).limit(1).execute().fetchone()[0]
    except TypeError:
        # something strange happened :/
        # just redirect to the begin of the topic
        return HttpResponseRedirect(href('forum', 'topic', topic_slug))
    return HttpResponseRedirect(Post.url_for_post(post_id))


@templated('forum/movetopic.html')
def movetopic(request, topic_slug):
    """Move a topic into another forum"""
    def _add_field_choices():
        """Add dynamic field choices to the move topic formular"""
        form.fields['forum_id'].choices = (
            (f.id, f.name[0] + u' ' + (u'   ' * offset) + f.name)
            for offset, f in Forum.get_children_recursive(Forum.query.all())
        )
        #TODO: add disabled="disabled" to categories and current forum
        #      (django doesn't feature that atm)

    topic = Topic.query.filter_by(slug=topic_slug).first()
    if not topic:
        raise PageNotFound
    if not have_privilege(request.user, topic.forum, CAN_MODERATE):
        return abort_access_denied(request)

    forums = filter_invisible(request.user, Forum.query.filter(and_(
        forum_table.c.parent_id != None, forum_table.c.id != topic.forum_id)))
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
            session.commit()
            # send a notification to the topic author to inform him about
            # the new forum.
            nargs = {
                'username':   topic.author.username,
                'topic':      topic,
                'mod':        request.user.username,
                'forum_name': forum.name
            }
            if 'topic_move' in topic.author.settings.get('notifications',
                                                         ('topic_move',)):
                send_notification(topic.author, 'topic_moved',
                    u'Dein Thema „%s“ wurde verschoben'
                    % topic.title, nargs)

            subscriptions = Subscription.objects.filter(Q(topic_id=topic.id) | Q(forum_id=forum.id))
            for subscription in subscriptions:
                if subscription.user.id == topic.author.id:
                    continue
                nargs['username'] = subscription.user.username
                notify_about_subscription(subscription, 'topic_moved',
                    u'Das Thema „%s“ wurde verschoben' % topic.title, nargs)
            return HttpResponseRedirect(url_for(topic))
    else:
        form = MoveTopicForm()
        _add_field_choices()
    return {
        'form':  form,
        'topic': topic
    }


@templated('forum/splittopic.html')
def splittopic(request, topic_slug):
    def _add_field_choices():
        """Add dynamic field choices to the move topic formular"""
        form.fields['forum'].choices = (
            (f.id, u'  ' * offset + f.name)
            for offset, f in Forum.get_children_recursive(Forum.query.all())
        )
        #TODO: add disabled="disabled" to categories and current forum
        #      (django doesn't feature that atm)

        form.fields['start'].choices = form.fields['select'].choices = \
            [(p.id, u'') for p in old_posts]

    old_topic = Topic.query.filter_by(slug=topic_slug).first()

    if not old_topic:
        raise PageNotFound

    if not have_privilege(request.user, old_topic.forum, CAN_MODERATE):
        return abort_access_denied(request)

    old_posts = old_topic.posts

    if request.method == 'POST':
        form = SplitTopicForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            data = form.cleaned_data

            if data['select_following']:
                posts = old_posts.filter(post_table.c.id >= data['start'])
            else:
                posts = old_posts.filter(post_table.c.id.in_(data['select']))

            posts = list(posts)

            if data['action'] == 'new':
                new_topic = Topic(
                    title=data['title'],
                    forum=data['forum'],
                    slug=None,
                    post_count=0,
                    author_id=posts[0].author_id
                )
                new_topic.forum.topic_count += 1
                session.flush([new_topic])
                Post.split(posts, old_topic, new_topic)
            else:
                new_topic = data['topic']
                Post.split(posts, old_topic, new_topic)

            session.commit()

            return HttpResponseRedirect(url_for(new_topic))
    else:
        form = SplitTopicForm(initial={'forum': old_topic.forum_id})
        _add_field_choices()

    return {
        'topic': old_topic,
        'forum': old_topic.forum,
        'posts': list(old_posts),
        'form':  form
    }


def hide_post(request, post_id):
    """
    Sets the hidden flag of a post to True which has the effect that normal
    users can't see it anymore (moderators still can).
    """
    post = Post.query.get(post_id)
    if not post:
        raise PageNotFound
    if not have_privilege(request.user, post.topic.forum, CAN_MODERATE):
        return abort_access_denied(request)
    if post.id == post.topic.first_post.id:
        if post.topic.post_count == 1:
            return HttpResponseRedirect(href('forum', 'topic',
                                             post.topic.slug, 'hide'))
        flash(u'Der erste Beitrag eines Themas darf nicht unsichtbar gemacht '
              u'werden', success=False)
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
    post = Post.query.get(post_id)
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
    if not have_privilege(request.user, post.topic.forum, CAN_MODERATE) and not\
       (post.author_id==request.user.id and post.check_ownpost_limit('delete')):
        flash(u'Du darfst diesen Beitrag nicht löschen!', False)
        return HttpResponseRedirect(href('forum', 'topic', post.topic.slug,
                                         post.page))
    if post.id == post.topic.first_post.id:
        if post.topic.post_count == 1:
            return HttpResponseRedirect(href('forum', 'topic',
                                             post.topic.slug, 'delete'))
        flash(u'Der erste Beitrag eines Themas darf nicht gelöscht werden!',
              success=False)

    else:
        if request.method == 'POST':
            if 'cancel' in request.POST:
                flash(u'Das Löschen wurde abgebrochen.')
            else:
                author = post.author
                session.delete(post)
                session.commit()
                last_post = Post.query.filter_by(topic_id=post.topic_id) \
                                      .order_by('-id').first()
                post.topic.last_post_id = last_post.id
                session.commit()
                flash(u'Der Beitrag von <a href="%s">%s</a> wurde gelöscht.'
                      % (url_for(author), escape(author.username)),
                      success=True)
        else:
            flash(render_template('forum/post_delete.html', {'post': post}))
    return HttpResponseRedirect(href('forum', 'topic', post.topic.slug,
                                     post.page))


@templated('forum/revisions.html')
def revisions(request, post_id):
    p = Post.query.options(eagerload('topic'), eagerload('topic.forum')) \
                  .get(post_id)
    if not have_privilege(request.user, p.topic.forum, CAN_MODERATE):
        return abort_access_denied(request)
    revs = PostRevision.query.filter(PostRevision.post_id == post_id)
    return {
        'post':      post,
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
    topic.forum.invalidate_topic_cache()
    return HttpResponseRedirect(url_for(topic))


def delete_topic(request, topic_slug):
    """
    In contrast to `hide_topic` this function does really remove the topic.
    This action is irrevocable and can only get executed by administrators.
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
            redirect = url_for(topic.forum)
            subscriptions = Subscription.objects.filter(topic_id=topic.id)
            sids = [s.id for s in subscriptions]
            for subscription in subscriptions:
                nargs = {
                    'username' : subscription.user.username,
                    'mod'      : request.user.username,
                    'topic'    : topic
                }
                notify_about_subscription(subscription, 'topic_deleted',
                    u'Das Thema „%s“ wurde gelöscht' % topic.title, nargs)
            session.delete(topic)
            session.commit()
            flash(u'Das Thema „%s“ wurde erfolgreich gelöscht' % topic.title,
                  success=True)
            return HttpResponseRedirect(redirect)
    else:
        flash(render_template('forum/delete_topic.html', {'topic': topic}))
    topic.forum.invalidate_topic_cache()
    return HttpResponseRedirect(url_for(topic))


@atom_feed()
def topic_feed(request, slug=None, mode='short', count=20):
    anonymous = User.objects.get_anonymous_user()

    topic = Topic.query.filter_by(slug=slug).first()

    if topic is None or topic.hidden:
        raise PageNotFound()
    if not have_privilege(anonymous, topic.forum, CAN_READ):
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
    anonymous = User.objects.get_anonymous_user()
    if slug:
        forum = Forum.query.get(slug)
        if forum is None:
            raise PageNotFound()
        if not have_privilege(anonymous, forum, CAN_READ):
            return abort_access_denied(request)

        topics = forum.get_latest_topics(count=count)
        title = u'ubuntuusers Forum – „%s“' % forum.name
        url = url_for(forum)
    else:
        allowed_forums = [f.id for f in filter_invisible(anonymous, Forum.query.all())]
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
        if topic.hidden:
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
        forum = Forum.query.get(slug)
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


@templated('forum/topiclist.html')
def newposts(request, page=1):
    """
    Return a list of the latest posts.
    """
    forum_ids = [f[0] for f in select([forum_table.c.id]).execute()]
    # get read status data
    data = request.user._readstatus.data

    def any(l):
        #TODO: Remove this when python version is 2.5+
        for e in l:
            if bool(e):
                return True
        return False

    #: sql where clause
    where = None

    # filter old topics with id < "last read post in this forum"
    if any(e[0] for e in data.itervalues()):
        ids = filter(lambda id: data[id][0] is not None, data.keys())
        where = or_(*[
            (
                (topic_table.c.forum_id == id) &
                (topic_table.c.last_post_id > data[id][0])
            ) for id in ids
        ] + [
            # don't filter in forums where "last read post" isn't set
            not_(topic_table.c.forum_id.in_(ids))
        ])

    # get single topics that are marked as "read"
    read_topics = []
    for id in forum_ids:
        read_topics.extend(data.get(id, [None, []])[1])

    # filter read topics
    if read_topics:
        cond = not_(topic_table.c.last_post_id.in_(read_topics))
        if where:
            where &= cond
        else:
            where = cond

    topics = Topic.query.options(eagerload('author'), eagerload('last_post'),
                                 eagerload('last_post.author')) \
        .filter(topic_table.c.sticky == False) \
        .order_by(topic_table.c.last_post_id.desc())

    if 'version' in request.GET:
        topics = topics.filter_by(ubuntu_version=request.GET['version'])

    # get the forums the user is not allowed to see
    forbidden_forums = []
    privs = get_privileges(request.user, forum_ids)
    for id in forum_ids:
        if privs.get(id, DISALLOW_ALL) & CAN_READ == 0:
            forbidden_forums.append(id)

    # don't show topics of forums where the user doesn't have CAN_READ
    # permission
    if forbidden_forums:
        topics = topics.filter(not_(topic_table.c.forum_id.in_(forbidden_forums)))

    if where:
        topics = topics.filter(where)

    pagination = Pagination(request, topics, page, 25,
        href('forum', 'newposts'))

    return {
        'topics':     list(pagination.objects),
        'pagination': pagination.generate('right'),
        'title':      u'Neue Beiträge',
        'get_read_status':  lambda post_id: request.user.is_authenticated \
                  and request.user._readstatus(forum_id=f.id, post_id=post_id),
    }


@templated('forum/topiclist.html')
def topiclist(request, page=1, action='newposts', hours=24, user=None):
    page = int(page)
    topics = Topic.query.order_by(topic_table.c.last_post_id.desc()) \
                  .options(eagerload('forum'),
                           eagerload('author'),
                           eagerload('last_post'),
                           eagerload('last_post.author'))

    if 'version' in request.GET:
        topics = topics.filter_by(ubuntu_version=request.GET['version'])

    if action == 'last':
        hours = int(hours)
        if hours > 24:
            raise PageNotFound()
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
    elif action == 'topic_author':
        user = User.objects.get(user)
        topics = topics.filter(Topic.author_id == user.id)
        url = href('forum', 'topic_author', user.username)
        title = u'Themen von %s' % (escape(user.username))
    elif action == 'author':
        user = user and User.objects.get(user) or request.user
        if user == User.objects.get_anonymous_user():
            raise PageNotFound()
        # get the ids of the topics the user has written posts in
        # we select TOPICS_PER_PAGE + 1 ones to see if there's another page.
        topic_ids = select([topic_table.c.id],
            exists([post_table.c.topic_id],
                (post_table.c.author_id == user.id) &
                (post_table.c.topic_id == topic_table.c.id)
            )
        ).order_by(topic_table.c.last_post_id.desc()) \
         .offset((page - 1) * TOPICS_PER_PAGE) \
         .limit(TOPICS_PER_PAGE + 1)

        topic_ids = [i[0] for i in topic_ids.execute().fetchall()]
        next_page = len(topic_ids) == TOPICS_PER_PAGE + 1
        topic_ids = topic_ids[:TOPICS_PER_PAGE]
        topics = filter(lambda x: have_privilege(request.user, x, 'read'),
                        list(topics.filter(topic_table.c.id.in_(topic_ids))))
        pagination = []
        normal = u'<a href="%(href)s" class="pageselect">%(text)s</a>'
        disabled = u'<span class="disabled next">%(text)s</span>'
        active = u'<span class="pageselect active">%(text)s</span>'
        pagination = [u'<div class="pagination pagination_right">']
        add = pagination.append

        if user != request.user:
            title = u'Beiträge von %s' % escape(user.username)
            url = href('forum', 'author', user.username)
        else:
            title = u'Eigene Beiträge'
            url = href('forum', 'egosearch')

        def _link(page):
            return '%s%d' % (url, page)

        add(((page == 1) and disabled or normal) % {
            'href': _link(page - 1),
            'text': u'« Zurück',
        })
        add(active % {
            'text': u'Seite %d' % page
        })
        add((next_page and normal or disabled) % {
            'href': _link(page + 1),
            'text': u'Weiter »'
        })
        add(u'<div style="clear: both"></div></div>')
        pagination = u''.join(pagination)

    if action != 'author':
        forum_ids = [f.id for f in filter_invisible(request.user,
                                                    Forum.query.all())]
        topics = topics.filter(topic_table.c.forum_id.in_(forum_ids))
        pagination = Pagination(request, topics, page, TOPICS_PER_PAGE, url)
        topics = pagination.objects
        pagination = pagination.generate()

    return {
        'topics':       list(topics),
        'pagination':   pagination,
        'title':        title,
        'get_read_status':  lambda post_id: request.user.is_authenticated \
                  and request.user._readstatus(post_id=post_id),
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
        session.commit()
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
