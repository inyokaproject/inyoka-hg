# -*- coding: utf-8 -*-
"""
    inyoka.forum.views
    ~~~~~~~~~~~~~~~~~~

    The views for the forum.

    :copyright: Copyright 2007 by Benjamin Wiegand, Christopher Grebs.
    :license: GNU GPL.
"""
import re
from django.utils.text import truncate_html_words
from sqlalchemy.orm import eagerload
from inyoka.conf import settings
from inyoka.portal.views import not_found as global_not_found
from inyoka.portal.utils import simple_check_login, abort_access_denied
from inyoka.utils.text import slugify
from inyoka.utils.urls import href, url_for, is_safe_domain
from inyoka.utils.html import escape
from inyoka.utils.sessions import set_session_info
from inyoka.utils.http import templated, does_not_exist_is_404, \
     PageNotFound, HttpResponse, HttpResponseRedirect
from inyoka.utils.feeds import FeedBuilder
from inyoka.utils.flashing import flash
from inyoka.utils.templating import render_template
from inyoka.utils.pagination import Pagination
from inyoka.utils.notification import send_notification
from inyoka.utils.cache import cache
from inyoka.utils.dates import format_datetime
from inyoka.wiki.utils import quote_text, normalize_pagename
from inyoka.wiki.models import Page as WikiPage
from inyoka.wiki.parser import parse, RenderContext
from inyoka.portal.models import Subscription
from inyoka.forum.models import Forum, Topic, Attachment, POSTS_PER_PAGE, \
     TOPICS_PER_PAGE, Post, get_ubuntu_version, Poll, WelcomeMessage, \
     SATopic, SAForum, SAPost
from inyoka.forum.forms import NewPostForm, NewTopicForm, SplitTopicForm, \
     AddAttachmentForm, EditPostForm, AddPollForm, MoveTopicForm, \
     ReportTopicForm, ReportListForm
from inyoka.forum.acl import filter_invisible, get_forum_privileges, \
                             have_privilege, get_privileges
from inyoka.forum.database import post_table, topic_table
from inyoka.forum.legacyurls import test_legacy_url


_legacy_forum_re = re.compile(r'^/forum/(\d+)(?:/(\d+))?/?$')


def not_found(request, err_message=None):
    """
    This is called if no URL matches or a view returned a `PageNotFound`.
    """
    response = test_legacy_url(request)
    if response is not None:
        return response
    return global_not_found(request, err_message)


@templated('forum/index.html')
def index(request, category=None):
    """
    Return all forums without parents.
    These forums are treated as categories but not as real forums.
    """
    categories = Forum.objects.get_categories(depth=1)
    if category:
        categories = [Forum.objects.get(slug=slugify(category))]
        if categories[0].parent_id:
            raise PageNotFound
        fmsg = categories[0].find_welcome(request.user)
        if fmsg is not None:
            return welcome(request, fmsg.slug, request.path)
        set_session_info(request, (u'sieht sich die Forenübersicht der '
                                   u'Kategorie „%s“ an'
                                   % categories[0].name),
                         u'Kategorieübersicht')
    else:
        set_session_info(request, u'sieht sich die Forenübersicht an.',
                         u'Forenübersicht')

    hidden_categories = []
    if request.user.is_authenticated:
        hidden_categories.extend(request.user.settings.get(
            'hidden_forum_categories', ()))

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
    f = Forum.objects.get(slug=slug)
    # if the forum is a category we raise PageNotFound.  categories have
    # their own url at /category.
    if f.parent_id is None:
        raise PageNotFound()
    privs = get_forum_privileges(request.user, f)
    if not privs['read']:
        return abort_access_denied(request)
    fmsg = f.find_welcome(request.user)
    if fmsg is not None:
        return welcome(request, fmsg.slug, request.path)
    page = int(page)
    key = 'forum/topics/%d/%d' % (f.id, int(page))
    data = cache.get(key)
    if not data:
        topics = SATopic.query.options(eagerload('author'), eagerload('last_post'),
            eagerload('last_post.author')).filter_by(forum_id=f.id) \
            .order_by((topic_table.c.sticky.desc(), topic_table.c.last_post_id.desc()))
        subforums = SAForum.query.options(eagerload('last_post'),
                eagerload('last_post.author')).filter_by(parent_id=f.id).all()
        pagination = Pagination(request, topics, page, TOPICS_PER_PAGE, url_for(f))
        data = {
            'forum':        f,
            'subforums':    subforums,
            'topics':       pagination.objects,
            'pagination':   pagination
        }
        # if you alter this value, change it in Post.delete too
        if page < 5:
            cache.set(key, data)
    set_session_info(request, u'sieht sich das Forum „<a href="%s">'
                     u'%s</a>“ an' % (escape(url_for(f)), escape(f.name)),
                     'besuche das Forum')
    data['subforums'] = filter_invisible(request.user, data['subforums'])
    data['privileges'] = privs

    if request.user.is_authenticated:
        key = 'subscription/forum/%d' % f.id
        subscribed = cache.get(key)
        if not subscribed:
             subscribed = Subscription.objects.filter(
                user=request.user, forum=f)
        data['is_subscribed'] = subscribed
        f.mark_read(request.user)
    return data


@templated('forum/topic.html')
def viewtopic(request, topic_slug, page=1):
    """
    Shows a topic, the posts are paginated.
    If the topic has a `hidden` flag, the user gets a nice message that the
    topic is deleted and is redirected to the topic's forum.  Moderators can
    see these topics.
    """
    t = Topic.objects.get(slug=topic_slug)
    privileges = get_forum_privileges(request.user, t.forum)
    if not privileges['read']:
        return abort_access_denied(request)
    if t.hidden:
        if not privileges['moderate']:
            # XXX: don't show the topic if the user isn't a moderator
            flash(u'Dieses Thema wurde von einem Moderator gelöscht.')
            return HttpResponseRedirect(url_for(t.forum))
        flash(u'Dieses Thema ist unsichtbar für normale Benutzer.')
    fmsg = t.forum.find_welcome(request.user)
    if fmsg is not None:
        return welcome(request, fmsg.slug, request.path)
    t.touch()

    posts = SAPost.query.options(eagerload('attachments')).filter(
        (SAPost.topic_id == t.id)
    )

    if t.has_poll:
        polls = Poll.objects.get_polls(t.id, request.user)

        if request.method == 'POST':
            # the user participated in a poll
            votings = []
            poll_ids = []
            for poll in polls.values():
                # get the votes for every poll in this topic
                if poll['multiple']:
                    v = request.POST.getlist('poll_%s' % poll['id'])
                else:
                    v = request.POST.get('poll_%s' % poll['id'])
                if v:
                    if not privileges['vote']:
                        return abort_access_denied(request)
                    elif poll['participated']:
                        flash(u'Du hast bereits an dieser Abstimmung '
                              u'teilgenommen.', False)
                        continue
                    def _vote(id):
                        # check whether the option selected is inside the
                        # right polls to prevent voting of other polls
                        if id in poll['options'] and id not in votings:
                            votings.append(id)
                            poll['options'][id]['votes'] += 1
                    if poll['multiple']:
                        for id in v:
                            _vote(int(id))
                    else:
                        _vote(int(v))
                    poll_ids.append(poll['id'])
                    poll['participated'] = True
                    flash(u'Deine Stimme wurde gespeichert.', True)

            if votings:
                # write the votes into the database
                Poll.objects.do_vote(request.user.id, votings, poll_ids)

        # calculate how many percent the options have of the total votes
        # this has to be done after voting
        Poll.objects.calculate_percentage(polls)
    else:
        polls = None

    pagination = Pagination(request, posts, page, POSTS_PER_PAGE, url_for(t))
    set_session_info(request, u'sieht sich das Thema „<a href="%s">%s'
        u'</a>“ an' % (url_for(t), escape(t.title)), 'besuche Thema')
    subscribed = False
    if request.user.is_authenticated:
        t.mark_read(request.user)
        subscribed = Subscription.objects.user_subscribed(request.user,
                                                          topic=t)
    return {
        'topic':        t,
        'forum':        t.forum,
        'posts':        pagination.objects,
        'privileges':   privileges,
        'is_subscribed':subscribed,
        'pagination':   pagination,
        'polls':        polls,
        'can_vote':     polls and (False in [p['participated'] for p in
                                             polls.values()]) or False,
        'show_vote_results': request.GET.get('action', '') == 'vote_results'
    }


@templated('forum/edit.html')
def newpost(request, topic_slug=None, quote_id=None):
    """
    If a user requests the page the first time, there is no POST-data and an
    empty form is displayed.  The action of the form is the view itself.
    If `quote_id` is an integer, the standard text is set to a quoted version
    of the post with id = `quote_id`.
    If a user submits the form, POST-data is set, and the form is validated.
    If validation fails, the form is displayed again with added error
    messages, else the post is saved and the user is forwarded to topic-view.
    """
    preview = quote = None

    if quote_id:
        quote = Post.objects.get(id=quote_id)
        t = quote.topic
    else:
        t = Topic.objects.get(slug=topic_slug)

    privileges = get_forum_privileges(request.user, t.forum)
    if t.locked and not privileges['moderate']:
        flash((u'Du kannst keinen Beitrag in diesem Thema erstellen, da es '
               u'von einem Moderator geschlossen wurde.'))
        return HttpResponseRedirect(t.get_absolute_url())
    elif not privileges['reply']:
        return abort_access_denied(request)
    posts = t.post_set.all().exclude(text='').order_by('-pub_date')[:10]
    attach_form = AddAttachmentForm()

    if request.method == 'POST':
        if 'cancel' in request.POST:
            flash('Antworten wurde abgebrochen.')
            return HttpResponseRedirect(t.get_absolute_url())

        form = NewPostForm(request.POST)
        att_ids = [int(id) for id in request.POST['att_ids'].split(',') if id]
        # check for post = None to be sure that the user can't "hijack"
        # other attachments.
        attachments = list(Attachment.objects.filter(id__in=att_ids,
                                                     post__isnull=True))
        if 'attach' in request.POST:
            if not privileges['upload']:
                return abort_access_denied(request)
            # the user uploaded a new attachment
            attach_form = AddAttachmentForm(request.POST, request.FILES)
            if attach_form.is_valid():
                d = attach_form.cleaned_data
                att_name = d.get('filename') or d['attachment'].filename
                att = Attachment.objects.create(
                    att_name, d['attachment'].content,
                    attachments, override=d['override']
                )
                if not att:
                    flash(u'Ein Anhang „%s“ existiert bereits' % att_name)
                else:
                    attachments.append(att)
                    att_ids.append(att.id)
                    flash(u'Der Anhang „%s“ wurde erfolgreich hinzugefügt'
                          % att_name)

        elif 'delete_attachment' in request.POST:
            if not (privileges['upload'] and privileges['delete']):
                return abort_access_denied(request)
            id = int(request.POST['delete_attachment'])
            att_ids.remove(id)
            att = filter(lambda a: a.id == id, attachments)[0]
            att.delete()
            attachments.remove(att)
            flash(u'Der Anhang „%s“ wurde gelöscht.' % att.name)

        elif 'preview' in request.POST:
            ctx = RenderContext(request)
            preview = parse(request.POST.get('text', '')).render(ctx, 'html')

        elif form.is_valid():
            data = form.cleaned_data
            post = t.reply(text=data['text'], author=request.user)
            Attachment.objects.update_post_ids(att_ids, post.id)
            t.save()
            # update cache
            for page in xrange(1, 5):
                cache.delete('forum/topics/%d/%d' % (t.forum_id, page))
            # send notifications
            for s in Subscription.objects.filter(topic=t,
                notified=False).exclude(user=request.user):
                text = render_template('mails/new_post.txt', {
                    'username': s.user.username,
                    'post':     post,
                    'topic':    t
                })
                send_notification(s.user, u'Neuer Beitrag im Thema „%s“'
                                % t.title, text)
                s.notified = True
                s.save()
            resp = HttpResponseRedirect(post.get_absolute_url())
            return resp
        form.data['att_ids'] = ','.join([unicode(id) for id in att_ids])
    else:
        if quote:
            text = quote_text(quote.text, quote.author)
            form = NewPostForm(initial={'text': text})
        else:
            form = NewPostForm()
        attachments = []

    set_session_info(request, u'schreibt einen neuen Beitrag in „<a href="'
                     u'%s">%s</a>“' % (escape(url_for(t)), escape(t.title)))
    return {
        'topic':       t,
        'forum':       t.forum,
        'posts':       list(posts),
        'form':        form,
        'attach_form': attach_form,
        'attachments': list(attachments),
        'can_attach':  privileges['upload'],
        'isnewpost' :  True,
        'preview':     preview
    }


@templated('forum/edit.html')
def newtopic(request, slug=None, article=None):
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
    preview = None

    if article:
        # the user wants to create a wiki discussion
        f = Forum.objects.get(slug=settings.WIKI_DISCUSSION_FORUM)
        article = WikiPage.objects.get(name=normalize_pagename(article))
        if request.method != 'POST':
            flash(u'Zu dem Artikel „%s“ existiert noch keine Diskussion. '
                  u'Wenn du willst, kannst du hier eine neue anlegen.' % \
                                                    (escape(article.name)))
    else:
        f = Forum.objects.get(slug=slug)
        if 0:# this is sooo annoying. request.method != 'POST':
            flash(u'<ul><li>Kennst du unsere <a href="%s">Verhaltensregeln</a'
                  u'>?</li><li>Kann das <a href="%s">Wiki</a> dir weiterhelfe'
                  u'n?</li><li>Hast du die <a href="%s">Suche</a> schon benut'
                  u'zt?</li><li>Benutze für lange Ausgaben und Quelltexte bit'
                  u'te unseren <a href="%s">NoPaste Service</a>.</li></ul>'
                  % (href('wiki', 'Verwaltung/Moderatoren-Team/Forenregeln'),
                     href('wiki'), href('portal', 'search'), href('pastebin'))
            )

    if f.parent is None:
        # we don't allow posting in categories
        return HttpResponseRedirect(href('forum'))

    privileges = get_forum_privileges(request.user, f)
    if not privileges['create']:
        return abort_access_denied(request)

    attach_form = AddAttachmentForm()
    poll_form = AddPollForm()

    if request.method == 'POST':
        form = NewTopicForm(request.POST)

        #: this is a list of the ids of the topic's attachments.
        att_ids = [int(id) for id in request.POST['att_ids'].split(',') if id]
        #: this is a list of the ids of the topic's polls
        poll_ids = [int(id) for id in request.POST['polls'].split(',') if id]

        # check for post / topic is null to be sure that the user can't
        # "hijack" other attachments / polls that are already bound to
        # another post / topic.
        attachments = list(Attachment.objects.filter(id__in=att_ids,
                                                     post__isnull=True))
        polls = list(Poll.objects.filter(id__in=poll_ids, topic__isnull=True))
        options = request.POST.getlist('options')

        if 'cancel' in request.POST:
            flash('Das Erstellen eines neuen Themas wurde abgebrochen.')
            return HttpResponseRedirect(f.get_absolute_url())

        elif 'attach' in request.POST:
            if not privileges['upload']:
                return abort_access_denied(request)
            # the user uploaded a new attachment
            attach_form = AddAttachmentForm(request.POST, request.FILES)
            if attach_form.is_valid():
                d = attach_form.cleaned_data
                att_name = d.get('filename') or d['attachment'].filename
                att = Attachment.objects.create(
                    att_name, d['attachment'].content,
                    attachments, override=d['override']
                )
                if not att:
                    flash(u'Ein Anhang „%s“ existiert bereits' % att_name)
                else:
                    attachments.append(att)
                    att_ids.append(att.id)
                    flash(u'Der Anhang „%s“ wurde erfolgreich hinzugefügt'
                          % att_name)

        elif 'delete_attachment' in request.POST:
            if not (privileges['upload'] and privileges['delete']):
                return abort_access_denied(request)
            id = int(request.POST['delete_attachment'])
            att_ids.remove(id)
            att = filter(lambda a: a.id == id, attachments)[0]
            att.delete()
            attachments.remove(att)
            flash(u'Der Anhang „%s“ wurde gelöscht.' % att.name)

        elif 'add_poll' in request.POST:
            # the user added a new poll
            if not privileges['create_poll']:
                return abort_access_denied(request)
            poll_form = AddPollForm(request.POST)
            if poll_form.is_valid():
                d = poll_form.cleaned_data
                poll = Poll.objects.create(d['question'], d['options'],
                                           multiple=d['multiple'])
                polls.append(poll)
                poll_ids.append(poll.id)
                flash(u'Die Umfrage „%s“ wurde erfolgreich erstellt' %
                      escape(poll.question), success=True)
                # clean the poll formular
                poll_form = AddPollForm()
                options = ['', '']

        elif 'add_option' in request.POST:
            if not privileges['create_poll']:
                return abort_access_denied(request)
            poll_form = AddPollForm(request.POST)
            options.append('')

        elif 'delete_poll' in request.POST:
            if not (privileges['create_poll'] and privileges['delete']):
                return abort_access_denied(request)
            # the user deleted a poll
            poll_id = int(request.POST['delete_poll'])
            poll = filter(lambda v: v.id == poll_id, polls)[0]
            poll.delete()
            polls.remove(poll)
            poll_ids.remove(poll_id)
            flash(u'Die Umfrage „%s“ wurde gelöscht' % escape(poll.question),
                  success=True)

        if 'preview' in request.POST:
            # just show the user a preview
            ctx = RenderContext(request)
            preview = parse(request.POST.get('text', '')).render(ctx, 'html')

        elif form.is_valid():
            data = form.cleaned_data
            # write the topic into the database
            topic = Topic.objects.create(f, data['title'], data['text'],
                        author=request.user, has_poll=bool(poll_ids),
                        ubuntu_distro=data['ubuntu_distro'],
                        ubuntu_version=data['ubuntu_version'],
                        sticky=data['sticky'])
            # bind all uploaded attachments to the new post
            Attachment.objects.update_post_ids(att_ids,
                                               topic.first_post_id)
            # bind all new polls to the new topic
            Poll.objects.update_topic_ids(poll_ids, topic.id)

            if article:
                # the topic is a wiki discussion, bind it to the wiki
                # article and send notifications.
                article.topic = topic
                article.save()

                for s in Subscription.objects.filter(wiki_page=article):
                    text = render_template('mails/new_page_discussion.txt', {
                        'username': s.user.username,
                        'page':     article
                    })
                    send_notification(s.user, (u'Neue Diskussion für die'
                        u' Seite „%s“ wurde eröffnet')
                        % article.title, text)
                    s.notified = True
                    s.save()
            else:
                # topic is a normal topic
                for s in Subscription.objects.filter(forum=f,
                    notified=False).exclude(user=request.user):
                    text = render_template('mails/new_topic.txt', {
                        'username' : s.user.username,
                        'forum' : f,
                        'topic' : topic,
                    })
                    send_notification(s.user, (u'Ein neues Thema wurde'
                        u'im Forum „%s“ eröffnet' % f.name), text)
                    s.notified = True
                    s.save()

            return HttpResponseRedirect(topic.get_absolute_url())

        form.data['att_ids'] = ','.join([unicode(id) for id in att_ids])
        form.data['polls'] = ','.join([unicode(id) for id in poll_ids])
    else:
        # try to get and preselect the user's ubuntu version
        ubuntu_version = get_ubuntu_version(request)
        form = NewTopicForm(initial={
            'ubuntu_version': ubuntu_version,
            'title':          article and article.name or ''
        })
        attachments = []
        polls = []
        options = ['', '']

    set_session_info(request, u'schreibt ein neues Thema in „<a href="%s">'
                     u'%s</a>“' % (escape(url_for(f)), escape(f.name)))
    return {
        'form':        form,
        'forum':       f,
        'attach_form': attach_form,
        'attachments': list(attachments),
        'can_attach':  privileges['upload'],
        'poll_form':   poll_form,
        'polls':       polls,
        'options':     options,
        'isnewtopic':  True,
        'article':     article,
        'preview':     preview
    }


@templated('forum/edit.html')
def edit(request, post_id):
    """
    The user can edit a post's text or add attachments on this page.
    If the post is the first post of a topic, the user also can edit the
    polls and the options (e.g.  sticky) of the topic.
    """
    post = Post.objects.get(id=post_id)
    #: the properties of the topic the user can edit when editing the topic's
    #: root post.
    topic_values = ['sticky', 'title', 'ubuntu_version', 'ubuntu_distro']
    privileges = get_forum_privileges(request.user, post.topic.forum)
    if not privileges['edit']:
        return abort_access_denied(request)
    is_first_post = post.topic.first_post_id == post.id
    attach_form = AddAttachmentForm()
    if is_first_post:
        poll_form = AddPollForm()
        polls = list(Poll.objects.filter(topic=post.topic))
        options = request.POST.getlist('options')
    attachments = list(Attachment.objects.filter(post=post))
    if request.method == 'POST':
        form = EditPostForm(request.POST, is_first_post=is_first_post)
        if 'attach' in request.POST:
            if not privileges['upload']:
                return abort_access_denied(request)
            attach_form = AddAttachmentForm(request.POST, request.FILES)
            if attach_form.is_valid():
                d = attach_form.cleaned_data
                att_name = d.get('filename') or d['attachment'].filename
                # check whether another attachment with the same name does
                # exist already
                try:
                    a = Attachment.objects.get(name=att_name, post=post)
                    if d['override']:
                        a.delete()
                        raise Attachment.DoesNotExist()
                    flash(u'Ein Anhang „%s“ existiert bereits' % att_name)
                except Attachment.DoesNotExist:
                    att = Attachment(
                        name=att_name,
                        post=post
                    )
                    att.save_file_file(att_name, d['attachment'].content)
                    att.save()
                    attachments.append(att)
                    flash(u'Der Anhang „%s“ wurde erfolgreich hinzugefügt'
                          % att_name)

        elif 'delete_attachment' in request.POST:
            if not (privileges['upload'] and privileges['delete']):
                return abort_access_denied(request)
            id = int(request.POST['delete_attachment'])
            att = filter(lambda a: a.id == id, attachments)[0]
            att.delete()
            attachments.remove(att)
            flash(u'Der Anhang „%s“ wurde gelöscht.' % att.name)

        elif is_first_post and 'add_poll' in request.POST:
            if not privileges['create_poll']:
                return abort_access_denied(request)
            # the user added a new poll
            poll_form = AddPollForm(request.POST)
            if poll_form.is_valid():
                d = poll_form.cleaned_data
                poll = Poll.objects.create(d['question'], d['options'],
                                           multiple=d['multiple'],
                                           topic_id=post.topic_id)
                polls.append(poll)
                if not post.topic.has_poll:
                    post.topic.has_poll = True
                    post.topic.save()
                flash(u'Die Umfrage „%s“ wurde erfolgreich erstellt' %
                      escape(poll.question), success=True)
                # clean the poll formular
                poll_form = AddPollForm()
                options = ['', '']

        elif is_first_post and 'add_option' in request.POST:
            if not privileges['create_poll']:
                return abort_access_denied(request)
            poll_form = AddPollForm(request.POST)
            options.append('')

        elif is_first_post and 'delete_poll' in request.POST:
            if not (privileges['create_poll'] and privileges['delete']):
                return abort_access_denied(request)
            # the user deleted a poll
            poll_id = int(request.POST['delete_poll'])
            poll = filter(lambda p: p.id == poll_id, polls)[0]
            poll.delete()
            polls.remove(poll)
            if not polls:
                post.topic.has_poll = False
                post.topic.save()
            flash(u'Die Umfrage „%s“ wurde gelöscht' % escape(poll.question),
                  success=True)
        elif form.is_valid():
            data = form.cleaned_data
            post.text = data['text']
            post.save()
            if is_first_post:
                for k in topic_values:
                    setattr(post.topic, k, data[k])
                post.topic.save()
            flash(u'Der Beitrag wurde erfolgreich bearbeitet')
            return HttpResponseRedirect(href('forum', 'post', post.id))
    else:
        initial = {'text': post.text}
        if is_first_post:
            for k in topic_values:
                initial[k] = getattr(post.topic, k)
        form = EditPostForm(initial=initial, is_first_post=is_first_post)

    d = {
        'form': form,
        'post': post,
        'attach_form': attach_form,
        'attachments': attachments,
        'isedit': True,
        'can_attach':  privileges['upload'],
    }
    if is_first_post:
        d.update({
            'isfirstpost': True,
            'poll_form': poll_form,
            'options': options or ['', ''],
            'polls': polls
        })
    return d


def change_status(request, topic_slug, solved=None, locked=None):
    """Change the status of a topic and redirect to it"""
    t = Topic.objects.get(slug=topic_slug)
    if not have_privilege(request.user, t.forum, 'read'):
        abort_access_denied(request)
    if solved is not None:
        t.solved = solved
        flash(u'Das Thema wurde als %s markiert' % (solved and u'gelöst' or \
                                                                u'ungelöst'))
    if locked is not None:
        t.locked = locked
        flash(u'Das Thema wurde %s' % (locked and u'gesperrt' or
                                                    u'entsperrt'))
    t.save()
    return HttpResponseRedirect(t.get_absolute_url())

def _generate_subscriber(obj, obj_slug, subscriptionkw, flasher):
    """
    Generates a subscriber-function to deal with objects of type `obj`
    which have the slug `slug` and are registered in the subscribtion by
    `subscriptionkw` and have the flashing-test `flasher`
    """
    @simple_check_login
    def subscriber(request, **kwargs):
        """
        If the user has already subscribed to this %s, it just redirects.
        If there isn't such a subscription, a new one is created.
        """ % obj_slug
        slug = kwargs[obj_slug]
        x = obj.objects.get(slug=slug)
        if not have_privilege(request.user, x, 'read'):
            return abort_access_denied(request)
        try:
            s = Subscription.objects.get(user=request.user, **{subscriptionkw : x})
        except Subscription.DoesNotExist:
            # there's no such subscription yet, create a new one
            Subscription(user=request.user,**{subscriptionkw : x}).save()
            flash(flasher)
        return HttpResponseRedirect(url_for(x))
    return subscriber

def _generate_unsubscriber(obj, obj_slug, subscriptionkw, flasher):
    """
    Generates an unsubscriber-function to deal with objects of type `obj`
    which have the slug `slug` and are registered in the subscribtion by
    `subscriptionkw` and have the flashing-test `flasher`
    """
    @simple_check_login
    def subscriber(request, **kwargs):
        """ If the user has already subscribed to this %s, this view removes it.
        """ % obj_slug
        slug = kwargs[obj_slug]
        x = obj.objects.get(slug=slug)
        if not have_privilege(request.user, x, 'read'):
            return abort_access_denied(request)
        try:
            s = Subscription.objects.get(user=request.user, **{subscriptionkw : x})
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
    t = Topic.objects.get(slug=topic_slug)
    if not have_privilege(request.user, t.forum, 'read'):
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
            t.reporter = request.user
            t.save()
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

    topics = Topic.objects.filter(reported__isnull=False)
    if request.method == 'POST':
        form = ReportListForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            d = form.cleaned_data
            Topic.objects.mark_as_done(d['selected'])
            topics = filter(lambda t: str(t.id) not in d['selected'], topics)
            flash(u'Die gewählten Themen wurden als bearbeitet markiert.',
                  True)
    else:
        form = ReportListForm()
        _add_field_choices()

    privileges = get_privileges(request.user, [x.forum for x in topics])
    visible_topics = []
    for topic in topics:
        if have_privilege(request.user, topic.forum, 'moderate'):
            visible_topics.append(topic)

    return {
        'topics':   visible_topics,
        'form':     form
    }


def post(request, post_id):
    """Redirect to the "real" post url" (see `PostManager.url_for_post`)"""
    rv = Post.objects.get_post_topic(int(post_id))
    if rv is None:
        raise PageNotFound()
    slug, page, post_id = rv
    url = href('forum', 'topic', slug, *(page != 1 and (page,) or ()))
    if request.GET:
        url += '?' + request.GET.urlencode()
    url += '#post-%d' % post_id
    return HttpResponseRedirect(url)


@templated('forum/movetopic.html')
def movetopic(request, topic_slug):
    """Move a topic into another forum"""
    def _add_field_choices():
        """Add dynamic field choices to the move topic formular"""
        form.fields['forum_id'].choices = [(f.id, f.name) for f in forums]

    t = Topic.objects.get(slug=topic_slug)
    if not have_privilege(request.user, t.forum, 'moderate'):
        return abort_access_denied()

    forums = filter_invisible(request.user, Forum.objects.get_forums()
                              .exclude(id=t.forum.id), 'read')
    mapping = dict((x.id, x) for x in forums)
    if not mapping:
        return abort_access_denied(request)

    if request.method == 'POST':
        form = MoveTopicForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            data = form.cleaned_data
            f = mapping.get(data['forum_id'])
            if f is None:
                return abort_access_denied(request)
            Topic.objects.move(t, f)
            # send a notification to the topic author to inform him about
            # the new forum.
            text = render_template('mails/topic_moved.txt', {
                'username':   t.author.username,
                'topic':      t,
                'mod':        request.user.username,
                'forum_name': f.name
            })
            if 'topic_move' in t.author.settings.get('notifications',
                                                     ('topic_move',)):
                send_notification(t.author, u'Dein Thema „%s“ wurde '
                                  u'verschoben' % t.title, text)
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
                                        Forum.objects.get_forums()]
        form.fields['start'].choices = form.fields['select'].choices = \
            [(p.id, u'') for p in posts]

    t = Topic.objects.get(slug=topic_slug)
    posts = t.post_set.all()
    if not have_privilege(request.user, t.forum, 'moderate'):
        return abort_access_denied(request)

    if request.method == 'POST':
        form = SplitTopicForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            data = form.cleaned_data
            if data['select_following']:
                p = Post.objects.filter(topic__id=t.id, id__gte=data['start'])
            else:
                p = Post.objects.filter(id__in=data['select'])

            if data['action'] == 'new':
                new = Post.objects.split(p, data['forum'],
                                         title=data['title'])
            else:
                new = Post.objects.split(p, topic_slug=data['topic_slug'])
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
    post = Post.objects.get(id=post_id)
    if not have_privilege(request.user, post.topic.forum, 'moderate'):
        return abort_access_denied(request)
    if post.id == post.topic.first_post.id:
        flash(u'Der erste Beitrag eines Themas darf nicht unsichtbar gemacht '
              u'werden.')
    else:
        post.hidden = True
        post.save()
        flash(u'Der Beitrag von „<a href="%s">%s</a>“ wurde unsichtbar '
              u'gemacht.' % (url_for(post), escape(post.author.username)),
              success=True)
    return HttpResponseRedirect(url_for(post).split('#')[0])


def restore_post(request, post_id):
    """
    This function removes the hidden flag of a post to make it visible for
    normal users again.
    """
    post = Post.objects.get(id=post_id)
    if not have_privilege(request.user, post.topic.forum, 'moderate'):
        return abort_access_denied(request)
    post.hidden = False
    post.save()
    flash(u'Der Beitrag von „<a href="%s">%s</a>“ wurde wieder sichtbar '
          u'gemacht.' % (url_for(post), escape(post.author.username)),
          success=True)
    return HttpResponseRedirect(url_for(post).split('#')[0])


def delete_post(request, post_id):
    """
    In contrast to `hide_post` this function does really remove this post.
    This action is irrevocable and can only get executed by administrators.
    """
    post = Post.objects.get(id=post_id)
    if not have_privilege(request.user, post.topic.forum, 'delete'):
        return abort_access_denied(request)
    if post.id == post.topic.first_post.id:
        flash(u'Der erste Beitrag eines Themas darf nicht unsichtbar gemacht '
              u'werden.', success=False)
    else:
        if request.method == 'POST':
            if 'cancel' in request.POST:
                flash(u'Das löschen wurde abgebrochen.')
            else:
                post.delete()
                flash(u'Der Beitrag von „<a href="%s">%s</a>“ wurde gelöscht.'
                      % (url_for(post), escape(post.author.username)),
                      success=True)
        else:
            flash(render_template('forum/post_delete.html', {'post': post}))
    return HttpResponseRedirect(url_for(post.topic))


def hide_topic(request, topic_slug):
    """
    Sets the hidden flag of a topic to True which has the effect that normal
    users can't see it anymore (moderators still can).
    """
    topic = Topic.objects.get(slug=topic_slug)
    if not have_privilege(request.user, topic.forum, 'moderate'):
        return abort_access_denied(request)
    topic.hidden = True
    topic.save()
    flash(u'Das Thema „%s“ wurde unsichtbar gemacht.' % topic.title,
          success=True)
    return HttpResponseRedirect(url_for(topic))


def restore_topic(request, topic_slug):
    """
    This function removes the hidden flag of a topic to make it visible for
    normal users again.
    """
    topic = Topic.objects.get(slug=topic_slug)
    if not have_privilege(request.user, topic.forum, 'moderate'):
        return abort_access_denied(request)
    topic.hidden = False
    topic.save()
    flash(u'Das Thema „%s“ wurde wieder sichtbar gemacht.' % topic.title,
          success=True)
    return HttpResponseRedirect(url_for(topic))


def delete_topic(request, topic_slug):
    """
    In contrast to `hide_topic` this function does really remove the topic.
    This action is irrevocable and can only get executed by administrators.
    """
    # XXX: Only administrators are allowed to do this, not moderators
    topic = Topic.objects.get(slug=topic_slug)
    if not have_privilege(request.user, topic.forum, 'moderate'):
        return abort_access_denied(request)

    if request.method == 'POST':
        if 'cancel' in request.POST:
            flash(u'Löschen des Themas „%s“ wurde abgebrochen' % topic.title)
        else:
            topic.delete()
            flash(u'Das Thema „%s“ wurde erfolgreich gelöscht' % topic.title,
                  success=True)
            return HttpResponseRedirect(url_for(topic.forum))
    else:
        flash(render_template('forum/delete_topic.html', {'topic': topic}))
    return HttpResponseRedirect(url_for(topic))


@does_not_exist_is_404
def feed(request, component='forum', slug=None, mode='short', count=25):
    """show the feeds for the forum"""

    if component not in ('forum', 'topic'):
        raise PageNotFound()

    if mode not in ('full', 'short', 'title'):
        raise PageNotFound()

    count = int(count)
    if count not in (5, 10, 15, 20, 25, 50, 75, 100):
        raise PageNotFound()

    key = 'forum/feeds/%s/%s/%s/%s' % (component, slug, mode, count)
    content = cache.get(key)
    if content is not None:
        content_type='application/atom+xml; charset=utf-8'
        return HttpResponse(content, content_type=content_type)

    if component == 'topic':
        topic = Topic.objects.get(slug=slug)
        if not have_privilege(request.user, topic.forum, 'read'):
            return abort_access_denied()
        posts = topic.post_set.order_by('-pub_date')[:count]
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
        if slug:
            forum = Forum.objects.get(slug=slug)
            if not have_privilege(request.user, forum, 'read'):
                return abort_access_denied()
            topics = forum.topic_set
            feed = FeedBuilder(
                title=u'ubuntuusers Forum – „%s“' % forum.name,
                url=url_for(forum),
                feed_url=request.build_absolute_uri(),
                rights=href('portal', 'lizenz'),
            )
        else:
            topics = Topic.objects.all()
            feed = FeedBuilder(
                title=u'ubuntuusers Forum',
                url=href('forum'),
                feed_url=request.build_absolute_uri(),
                rights=href('portal', 'lizenz'),
            )

        topics = topics.order_by('-id')[:count]

        for topic in topics:
            kwargs = {}
            post = topic.first_post
            if mode == 'full':
                kwargs['content'] = u'<div xmlns="http://www.w3.org/1999/' \
                                    u'xhtml">%s</div>' % post.rendered_text
                kwargs['content_type'] = 'xhtml'
            if mode == 'short':
                summary = truncate_html_words(post.rendered_text, 100)
                kwargs['summary'] = u'<div xmlns="http://www.w3.org/1999/' \
                                    u'xhtml">%s</div>' % summary
                kwargs['content_type'] = 'xhtml'

            feed.add(
                title=topic.title,
                url=url_for(topic),
                author=topic.author,
                published=post.pub_date,
                updated=post.pub_date,
                **kwargs
            )

    response = feed.get_atom_response()
    cache.set(key, response.content, 600)
    return response


def markread(request, slug=None):
    """
    Mark either all or only the given forum as read.
    """
    user = request.user
    if user.is_anonymous:
        return
    if slug:
        forum = Forum.objects.get(slug=slug)
        forum.mark_read(user)
        flash(u'Das Forum „%s“ wurde als gelesen markiert.' % forum.name)
        return HttpResponseRedirect(url_for(forum))
    else:
        flash(u'Allen Foren wurden als gelesen markiert.')
        user.forum_last_read = Post.objects.get_max_id()
        user.forum_read_status = ''
        user.save()
        # to trigger subscriptions
        for forum in Forum.objects.all():
            forum.mark_read(user)
    return HttpResponseRedirect(href('forum'))


@templated('forum/newposts.html')
def newposts(request, page=1):
    """
    Return a list of the latest posts.
    """
    privs = get_privileges(request.user, Forum.objects.all())
    all_topics = cache.get('forum/lasttopics')
    if not all_topics:
        all_topics = list(SATopic.query.options(eagerload('author'), \
            eagerload('last_post'), eagerload('last_post.author')) \
            .order_by((topic_table.c.last_post_id.desc()))[:80])
        cache.set('forum/lasttopics', all_topics)
    topics = []
    for topic in all_topics:
        if topic.last_post_id < request.user.forum_last_read:
            break
        if privs.get(topic.forum_id, {}).get('read', False):
            topics.append(topic)
    pagination = Pagination(request, topics, page, 20,
        href('forum', 'newposts'))
    return {
        'posts': pagination.objects,
        'pagination': pagination
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
        target_url = request.POST.get('goto_url')
        if accepted and target_url and is_safe_domain(target_url):
            return HttpResponseRedirect(request.POST.get('goto_url'))
        return HttpResponseRedirect(href('forum'))
    return {
        'goto_url': goto_url,
        'message': forum.welcome_message,
        'forum': forum
    }
