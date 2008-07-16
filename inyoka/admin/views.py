#-*- coding: utf-8 -*-
"""
    inyoka.portal.admin
    ~~~~~~~~~~~~~~~~~~~

    This module holds the admin views.

    :copyright: 2008 by Christopher Grebs, Benjamin Wiegand.
    :license: GNU GPL.
"""
import os
import pytz
from os import path
from PIL import Image
from StringIO import StringIO
from sqlalchemy import not_, and_, select
from copy import copy as ccopy
from datetime import datetime, date
from django.newforms.models import model_to_dict
from django.newforms.util import ErrorList
from inyoka.conf import settings
from inyoka.utils.text import slugify
from inyoka.utils.http import templated
from inyoka.utils.cache import cache
from inyoka.utils.urls import url_for, href, global_not_found
from inyoka.utils.flashing import flash
from inyoka.utils.templating import render_template
from inyoka.utils.html import escape
from inyoka.utils.http import HttpResponse, HttpResponseRedirect, \
     PageNotFound
from inyoka.utils.sortable import Sortable
from inyoka.utils.storage import storage
from inyoka.utils.pagination import Pagination
from inyoka.utils.database import session as dbsession
from inyoka.utils.dates import datetime_to_naive_utc, datetime_to_timezone, \
     get_user_timezone
from inyoka.admin.forms import EditStaticPageForm, EditArticleForm, \
     EditBlogForm, EditCategoryForm, EditFileForm, ConfigurationForm, \
     EditUserForm, EditEventForm, EditForumForm, EditGroupForm, \
     CreateUserForm, EditStyleForm
from inyoka.portal.models import StaticPage, Event, StaticFile
from inyoka.portal.user import User, Group, PERMISSION_NAMES, PERMISSION_MAPPING
from inyoka.portal.utils import require_permission
from inyoka.planet.models import Blog
from inyoka.ikhaya.models import Article, Suggestion, Category
from inyoka.forum.acl import PRIVILEGES_DETAILS, PRIVILEGES_BITS, \
    join_flags, split_flags
from inyoka.forum.models import Forum, Privilege, WelcomeMessage
from inyoka.forum.database import forum_table, privilege_table, \
    user_group_table
from inyoka.wiki.parser import parse, RenderContext


def not_found(request, err_message=None):
    """
    Displayed if a url does not match or a view tries to display a not
    exising resource.
    """
    return global_not_found(request, 'admin', err_message)


@require_permission('admin_panel')
@templated('admin/index.html')
def index(request):
    return {}


@require_permission('configuration_edit')
@templated('admin/configuration.html')
def config(request):
    keys = ['max_avatar_width', 'max_avatar_height', 'max_signature_length',
            'max_signature_lines', 'get_ubuntu_link', 'global_message',
            'get_ubuntu_description', 'blocked_hosts', 'wiki_newpage_template',
            'wiki_newpage_root']
    if request.method == 'POST':
        form = ConfigurationForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            for k in keys:
                storage[k] = data[k]
            if data['team_icon']:
                img_data = data['team_icon'].read()
                icon = Image.open(StringIO(img_data))
                fn = 'portal/team_icon.%s' % icon.format.lower()
                imgp = path.join(settings.MEDIA_ROOT, fn)

                if path.exists(imgp):
                    os.remove(imgp)

                f = open(imgp, 'wb')
                try:
                    f.write(img_data)
                finally:
                    f.close()

                storage['team_icon'] = fn

            flash(u'Die Einstellungen wurden gespeichert.', True)
            return HttpResponseRedirect(href('admin', 'config'))
    else:
        form = ConfigurationForm(initial=storage.get_many(keys))
    return {
        'form': form
    }


@require_permission('static_page_edit')
@templated('admin/pages.html')
def pages(request):
    sortable = Sortable(StaticPage.objects.all(), request.GET, '-key')
    return {
        'table': sortable,
        'pages': sortable.get_objects(),
    }


@require_permission('static_page_edit')
@templated('admin/pages_edit.html')
def pages_edit(request, page=None):
    if page:
        page = StaticPage.objects.get(key=page)
        form = EditStaticPageForm(model_to_dict(page))
    else:
        form = EditStaticPageForm()

    if request.method == 'POST':
        form = EditStaticPageForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            title = data['title']
            key = data['key'] or slugify(title)
            content = data['content']
            if not page:
                page = StaticPage(
                    key=key,
                    title=title,
                    content=content
                )
                flash(u'Die Seite „<a href="%s">%s</a>“ '
                      u'wurde erfolgreich erstellt.' % (
                        url_for(page), escape(page.title)))
            else:
                page.key = key
                page.title = title
                page.content = content
                flash(u'Die Seite „<a href="%s">%s</a>“ '
                      u'wurde erfolgreich editiert.' % (
                        url_for(page), escape(page.title)))
            page.save()
            return HttpResponseRedirect(href('admin', 'pages'))

    return {
        'form': form,
        'page': page
    }


@require_permission('static_page_edit')
def pages_delete(request, page_key):
    if not page_key:
        flash(u'Es wurde keine Seite zum löschen ausgewählt.')
    page = StaticPage.objects.get(key=page_key)
    if request.method == 'POST':
        if 'cancel' in request.POST:
            flash(u'Löschen abgebrochen')
        else:
            page.delete()
            flash(u'Die Seite „%s“ wurde erfolgreich gelöscht'
                  % escape(page.title))
    else:
        flash(render_template('admin/pages_delete.html', {
                'page': page}))
    return HttpResponseRedirect(href('admin', 'pages'))


@require_permission('static_file_edit')
@templated('admin/files.html')
def files(request):
    sortable = Sortable(StaticFile.objects.all(), request.GET, 'identifier')
    return {
        'table': sortable
    }


@require_permission('static_file_edit')
@templated('admin/file_edit.html')
def file_edit(request, file=None):
    """
    Display an interface to let the user create or edit a static file.
    """
    new = not bool(file)
    if file:
        file = StaticFile.objects.get(identifier=file)

    if request.method == 'POST':
        form = EditFileForm(file, request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            if not file:
                file = StaticFile()
            if data['file']:
                file.save_file_file(data['file'].name, data['file'].read())
                file.identifier = data['file'].name
            file.is_ikhaya_icon = data['is_ikhaya_icon']
            file.save()
            flash(u'Die statische Datei wurde geändert.', True)
            if new:
                return HttpResponseRedirect(file.get_absolute_url('edit'))
    else:
        initial = {}
        if file:
            initial = {
                'identifier':       file.identifier,
                'is_ikhaya_icon':   file.is_ikhaya_icon
            }
        form = EditFileForm(initial=initial)
    return {
        'form':   form,
        'file':   file
    }


@require_permission('blog_edit')
@templated('admin/planet.html')
def planet(request):
    return {
        'blogs': Blog.objects.all(),
    }


@require_permission('blog_edit')
@templated('admin/planet_edit.html')
def planet_edit(request, blog=None):
    if blog:
        blog = Blog.objects.get(id=blog)
        new = False
    else:
        new = True

    if request.method == 'POST':
        form = EditBlogForm(request.POST, request.FILES)
        if form.is_valid():
            d = form.cleaned_data
            if not blog:
                blog = Blog()
            for k in ('name', 'description', 'blog_url', 'feed_url'):
                setattr(blog, k, d[k])
            if d['delete_icon']:
                blog.delete_icon()
            if d['icon']:
                blog.save()
                blog.save_icon(d['icon'])
            blog.save()
            if new:
                flash(u'Der Blog „<a href="%s">%s</a>“ '
                      u'wurde erfolgreich erstellt.' % (
                        url_for(blog), escape(blog.name)))
            else:
                flash(u'Der Blog „<a href="%s">%s</a>“ '
                      u'wurde erfolgreich editiert.' % (
                        url_for(blog), escape(blog.name)))
            return HttpResponseRedirect(href('admin', 'planet'))
    else:
        if blog:
            form = EditBlogForm(initial=model_to_dict(blog))
        else:
            form = EditBlogForm()

    return {
        'form': form,
        'blog': blog
    }


@require_permission('article_edit', 'category_edit', 'event_edit')
@templated('admin/ikhaya.html')
def ikhaya(request):
    return {}


@require_permission('article_edit')
@templated('admin/ikhaya_articles.html')
def ikhaya_articles(request, page=1):
    sortable = Sortable(Article.objects.all(), request.GET, '-pub_date')
    pagination = Pagination(request, sortable.get_objects(), page, 25)
    return {
        'table': sortable,
        'articles': list(pagination.objects),
        'pagination': pagination
    }


@require_permission('article_edit')
@templated('admin/ikhaya_article_edit.html')
def ikhaya_article_edit(request, article=None, suggestion_id=None):
    """
    Display an interface to let the user create or edit an article.
    If `suggestion_id` is given, the new ikhaya article is based on a special
    article suggestion made by a user.  After saving it, the suggestion will be
    deleted automatically.
    """
    preview = None

    def _add_field_choices():
        categories = [(c.id, c.name) for c in Category.objects.all()]
        icons = [(i.id, i.identifier)
                 for i in StaticFile.objects.filter(is_ikhaya_icon=True)]
        form.fields['icon_id'].choices = [(u'', u'')] + icons
        form.fields['category_id'].choices = categories

    if article:
        article = Article.objects.get(slug=article)

    if request.method == 'POST':
        form = EditArticleForm(request.POST)
        if 'send' in request.POST:
            _add_field_choices()
            if form.is_valid():
                data = form.cleaned_data
                data['author'] = data['author'] or request.user
                data['pub_date'] = get_user_timezone().localize(
                    data['pub_date']).astimezone(pytz.utc).replace(tzinfo=None)
                if not data.get('icon_id'):
                    data['icon_id'] = None
                if not article:
                    article = Article(**data)
                    article.save()
                    if suggestion_id:
                        Suggestion.objects.delete([suggestion_id])
                    flash(u'Der Artikel „%s“ wurde erstellt.'
                          % escape(article.subject), True)
                    return HttpResponseRedirect(article.get_absolute_url('edit'))
                else:
                    changed = False
                    for k in data:
                        if article.__getattribute__(k) != data[k]:
                            article.__setattr__(k, data[k])
                            changed = True
                    if changed:
                        article.updated = datetime.utcnow()
                        article.save()
                        flash(u'Der Artikel „%s“ wurde geändert.'
                              % escape(article.subject), True)
                    else:
                        flash(u'Der Artikel „%s“ wurde nicht verändert'
                              % escape(article.subject))
        elif 'preview' in request.POST:
            ctx = RenderContext(request)
            preview = parse('%s\n\n%s' % (request.POST.get('intro', ''),
                            request.POST.get('text'))).render(ctx, 'html')
    else:
        initial = {}
        if article:
            initial = {
                'subject': article.subject,
                'intro': article.intro,
                'text': article.text,
                'author': article.author,
                'category_id': article.category.id,
                'icon_id': article.icon and article.icon.id or None,
                'pub_date': datetime_to_timezone(article.pub_date).replace(tzinfo=None),
                'public': article.public,
                'slug': article.slug,
                'comments_enabled': article.comments_enabled,
            }
        elif suggestion_id:
            suggestion = Suggestion.objects.get(id=suggestion_id)
            initial = {
                'subject': suggestion.title,
                'text':    suggestion.text,
                'intro':   suggestion.intro
            }
        form = EditArticleForm(initial=initial)
        _add_field_choices()

    return {
        'form': form,
        'article': article,
        'preview': preview,
    }


@require_permission('article_edit')
def ikhaya_article_delete(request, article):
    article = Article.objects.get(slug=article)
    if request.method == 'POST':
        if 'unpublish' in request.POST:
            article.public = False
            article.save()
            flash(u'Die Veröffentlichung des Artikels „<a href="%s">%s</a>“'
                  ' wurde aufgehoben.'
                  % (escape(url_for(article, 'show')), escape(article.subject)))
        elif 'cancel' in request.POST:
            flash(u'Löschen des Artikels „<a href="%s">%s</a>“ wurde abgebrochen'
                  % (escape(url_for(article, 'show')), escape(article.subject)))
        else:
            article.delete()
            flash(u'Der Artikel „%s“ wurde erfolgreich gelöscht'
                  % escape(article.subject))
    else:
        flash(render_template('admin/ikhaya_article_delete.html',
              {'article': article}))
    return HttpResponseRedirect(href('admin', 'ikhaya', 'articles'))


@require_permission('category_edit')
@templated('admin/ikhaya_categories.html')
def ikhaya_categories(request):
    sortable = Sortable(Category.objects.all(), request.GET, '-name')
    return {
        'table': sortable
    }


@require_permission('category_edit')
@templated('admin/ikhaya_category_edit.html')
def ikhaya_category_edit(request, category=None):
    """
    Display an interface to let the user create or edit an category.
    """
    def _add_field_choices():
        icons = [(i.id, i.identifier)
                 for i in StaticFile.objects.filter(is_ikhaya_icon=True)]
        form.fields['icon'].choices = icons

    if category:
        category = Category.objects.get(slug=category)

    if request.method == 'POST':
        form = EditCategoryForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            data = form.cleaned_data
            data['icon_id'] = data.pop('icon')
            if not category:
                category = Category(**form.cleaned_data)
                category.save()
                flash(u'Die Kategorie „%s“ wurde erstellt'
                      % escape(category.name), True)
            else:
                for k in data:
                    if category.__getattribute__(k) != data[k]:
                        category.__setattr__(k, data[k])
                category.save()
                flash(u'Die Kategorie „%s“ wurde geändert.'
                      % escape(category.name), True)
            return HttpResponseRedirect(href('admin', 'ikhaya', 'categories'))
    else:
        initial = {}
        if category:
            initial = {
                'name': category.name,
                'icon': category.icon_id
            }
        form = EditCategoryForm(initial=initial)
        _add_field_choices()

    return {
        'form': form,
        'category': category
    }


@require_permission('event_edit')
@templated('admin/ikhaya_dates.html')
def ikhaya_dates(request):
    sortable = Sortable(Event.objects.all(), request.GET, 'title')
    return {
        'table': sortable
    }


@require_permission('event_edit')
@templated('admin/ikhaya_date_edit.html')
def ikhaya_date_edit(request, date=None):
    """
    Display an interface to let the user create or edit a date.
    """
    if date:
        date = Event.objects.get(id=date)
    if request.method == 'POST':
        form = EditDateForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if not date:
                date = Event()
            date.date = data['date']
            date.title = data['title']
            date.author_id = request.user.id
            date.description = data['description']
            date.save()
            flash(u'Die Veranstaltung „%s“ wurde geändert.'
                  % escape(date.title), True)
            return HttpResponseRedirect(href('admin', 'ikhaya', 'dates'))
    else:
        initial = {}
        if date:
            initial = {
                'title': date.title,
                'description': date.description,
                'date': date.date
            }
        form = EditDateForm(initial=initial)

    return {
        'form': form,
        'date': date
    }


@require_permission('forum_edit')
@templated('admin/forums.html')
def forums(request):
    sortable = Sortable(Forum.query, request.GET, '-name',
        sqlalchemy=True, sa_column=forum_table.c.name)
    return {
        'table': sortable
    }


@require_permission('forum_edit')
@templated('admin/forum_edit.html')
def forum_edit(request, id=None):
    """
    Display an interface to let the user create or edit an forum.
    If `id` is given, the forum with id `id` will be edited.
    """
    def _add_field_choices():
        if id:
            query = Forum.query.filter(forum_table.c.id!=id)
        else:
            query = Forum.query.all()
        categories = [(c.id, c.name) for c in query]
        form.fields['parent'].choices = [(-1, "-")] + categories

    forum = None
    errors = False

    if id:
        forum = Forum.query.get(int(id))
        if forum is None:
            raise PageNotFound()

    if request.method == 'POST':
        form = EditForumForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            data = form.cleaned_data
            slug = data['slug']
            if Forum.query.filter(and_(Forum.slug == slug, Forum.id != id)).first():
                form.errors['slug'] = (
                    (u'Bitte einen anderen Slug angeben,'
                     u'„%s“ ist schon vergeben.'
                     % escape(data['slug'])),
                )
                errors = True
            if not id:
                forum = Forum()
            forum.name = data['name']
            forum.position = data['position']
            old_slug = forum.slug
            forum.slug = slug
            forum.description = data['description']
            if int(data['parent']) != -1:
                parent = Forum.query.get(int(data['parent']))
                if not parent:
                    form.errors['parent'] = (u'Forum %s existiert nicht'
                                             % escape(data['parent']),)
                else:
                    forum.parent = parent

            if data['welcome_msg_subject']:
                # subject and text are bound to each other, validation
                # is done in admin.forms
                welcome_msg = WelcomeMessage(
                    title=data['welcome_msg_subject'],
                    text=data['welcome_msg_text']
                )
                welcome_msg.save()
                forum.welcome_message_id = welcome_msg.id

            if not form.errors and not errors:
                dbsession.commit()
                keys = ['forum/index'] + ['forum/forum/' + f.slug
                                          for f in forum.parents]
                if old_slug is not None:
                    keys.append('forum/forum/' + old_slug)
                cache.delete_many(*keys)
                flash(u'Das Forum „%s“ wurde erfolgreich %s' % (
                      escape(forum.name), not id and 'angelegt' or 'editiert'))
                return HttpResponseRedirect(href('admin', 'forum'))
            else:
                flash(u'Es sind Fehler aufgetreten, bitte behebe sie.', False)

    else:
        if id is None:
            form = EditForumForm()
        else:
            welcome_msg = None
            if forum.welcome_message_id:
                welcome_msg = WelcomeMessage.query.get(forum.welcome_message_id)

            form = EditForumForm({
                'name': forum.name,
                'slug': forum.slug,
                'description': forum.description,
                'parent': forum.parent_id,
                'position': forum.position,
                'welcome_msg_subject': welcome_msg and welcome_msg.title or u'',
                'welcome_msg_text': welcome_msg and welcome_msg.text or u''
            })
        _add_field_choices()
    return {
        'form':  form,
        'forum': forum
    }


@require_permission('user_edit')
@templated('admin/users.html')
def users(request):
    if request.method == 'POST':
        name = request.POST.get('user')
        try:
            user = User.objects.get(username=name)
        except User.DoesNotExist:
            flash(u'Der Benutzer „%s“ existiert nicht.'
                  % escape(name))
        else:
            return HttpResponseRedirect(href('admin', 'users', 'edit', name))
    return {}


@require_permission('user_edit')
@templated('admin/user_edit.html')
def user_edit(request, username):
    #: check if the user exists
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        flash(u'Der Benutzer „%s“ existiert nicht.'
              % escape(username))
        return HttpResponseRedirect(href('admin', 'users'))

    groups = dict((g.name, g) for g in Group.objects.all())
    groups_joined, groups_not_joined = ([], [])
    checked_perms = [int(p) for p in request.POST.getlist('permissions')]

    if request.method == 'POST':
        form = EditUserForm(request.POST, request.FILES)
        form.fields['permissions'].choices = [(k, '') for k in
                                              PERMISSION_NAMES.keys()]
        if form.is_valid():
            data = form.cleaned_data
            if data['username'] != user.username:
                try:
                    User.objects.get(username=data['username'])
                except User.DoesNotExist:
                    user.username = data['username']
                else:
                    form.errors['username'] = ErrorList([u'Ein Benutzer mit '
                        u'diesem Namen existiert bereits'])
        if form.is_valid():
            #: set the user attributes, avatar and forum privileges
            for key in ('is_active', 'date_joined',
                        'website', 'interests', 'location', 'jabber', 'icq',
                        'msn', 'aim', 'yim', 'signature', 'coordinates_long',
                        'coordinates_lat', 'gpgkey', 'email', 'skype', 'sip',
                        'wengophone', 'member_title', 'launchpad'):
                setattr(user, key, data[key])
            if data['delete_avatar']:
                user.delete_avatar()

            if data['avatar']:
                user.save_avatar(data['avatar'])

            if data['new_password']:
                user.set_password(data['new_password'])

            if data['banned'] != user.banned:
                user.banned = data['banned']

            # permissions
            permissions = 0
            for perm in checked_perms:
                permissions |= perm
            user._permissions = permissions

            #: forum privileges
            privileges = Privilege.query
            for key, value in request.POST.iteritems():
                if key.startswith('forum_privileges-'):
                    forum_id = key.split('-', 1)[1]
                    privilege = privileges.filter(and_(
                        privilege_table.c.forum_id==forum_id,
                        privilege_table.c.group_id==None,
                        privilege_table.c.user_id==user.id
                    )).first()
                    if privilege is None:
                        privilege = Privilege(
                            user=user,
                            forum=Forum.query.get(int(forum_id))
                        )
                        dbsession.save(privilege)
                    privilege.bits = join_flags(*value)
                    dbsession.flush()

            # group editing
            groups_joined = [groups[gn] for gn in
                             request.POST.getlist('user_groups_joined')]
            groups_not_joined = [groups[gn] for gn in
                                request.POST.getlist('user_groups_not_joined')]
            user.groups.remove(*groups_not_joined)
            user.groups.add(*groups_joined)

            # save the user object back to the database as well as other
            # database changes
            user.save()
            dbsession.commit()
            cache.delete('user_permissions/%s' % user.id)

            flash(u'Das Benutzerprofil von "%s" wurde erfolgreich aktualisiert!'
                  % escape(user.username), True)
            # redirect to the new username if given
            if user.username != username:
                return HttpResponseRedirect(href('admin', 'users', 'edit', user.username))
        else:
            flash(u'Es sind Fehler aufgetreten, bitte behebe sie!', False)
    else:
        form = EditUserForm(initial=model_to_dict(user))

    # collect forum privileges
    forum_privileges = []
    forums = Forum.query.all()
    for forum in forums:
        privilege = Privilege.query.filter(and_(
            privilege_table.c.forum_id==forum.id,
            privilege_table.c.user_id==user.id
        )).first()

        forum_privileges.append((
            forum.id,
            forum.name,
            list(split_flags(privilege and privilege.bits or None))
        ))

    groups_joined = groups_joined or user.groups.all()
    groups_not_joined = groups_not_joined or \
                        [x for x in groups.itervalues() if not x in groups_joined]

    storage_data = storage.get_many(('max_avatar_height', 'max_avatar_width'))

    permissions = []

    groups = request.user.groups.all()
    for id, name in PERMISSION_NAMES.iteritems():
        derived = filter(lambda g: id & g.permissions, groups)
        if request.method == 'POST':
            checked = id in checked_perms
        else:
            checked = id & request.user._permissions
        permissions.append((id, name, checked, derived))

    return {
        'user': user,
        'form': form,
        'user_forum_privileges': forum_privileges,
        'forum_privileges': PRIVILEGES_DETAILS,
        'joined_groups': [g.name for g in groups_joined],
        'not_joined_groups': [g.name for g in groups_not_joined],
        'avatar_height': storage_data['max_avatar_height'],
        'avatar_width': storage_data['max_avatar_width'],
        'permissions': sorted(permissions, key=lambda p: p[1]),
    }


@require_permission('user_edit')
@templated('admin/user_new.html')
def user_new(request):
    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            u = User.objects.register_user(
                username=data['username'],
                email=data['email'],
                password=data['password'],
                send_mail=data['authenticate']
            )
            flash(u'Der Bentuzer „%s“ wurde erfolgreich erstellt'
                  % escape(data['username']), True)
            flash(u'Du kannst nun weitere Details bearbeiten')
            return HttpResponseRedirect(href('admin', 'users', 'edit',
                                             escape(data['username'])))
        else:
            flash(u'Es sind Probleme aufgetreten, bitte behebe sie!', False)
    else:
        form = CreateUserForm()
    return {
        'form': form
    }


@require_permission('group_edit')
@templated('admin/groups.html')
def groups(request):
    if request.method == 'POST':
        name = request.POST.get('group')
        try:
            group = Group.objects.get(name=name)
        except Group.DoesNotExist:
            flash(u'Die Gruppe „%s“ existiert nicht.'
                  % escape(name), False)
        else:
            return HttpResponseRedirect(href(
                'admin', 'groups', 'edit', name
            ))
    groups = Group.objects.all()
    return {
        'groups': groups,
        'groups_exist': len(groups),
    }


@require_permission('group_edit')
@templated('admin/group_edit.html')
def group_edit(request, name=None):
    def _add_choices(form):
        form.fields['permissions'].choices = sorted(
            [(k, v) for k, v in PERMISSION_NAMES.iteritems()],
            key=lambda p: p[1]
        )
    new = name is None
    changed_permissions = False
    if new:
        group = Group()
    else:
        try:
            group = Group.objects.get(name=name)
        except Group.DoesNotExist:
            flash(u'Die Gruppe „%s“ existiert nicht.'
                  % escape(name), False)
            return HttpResponseRedirect(href('admin', 'groups'))

    if request.method == 'POST':
        form = EditGroupForm(request.POST)
        _add_choices(form)
        if form.is_valid():
            data = form.cleaned_data
            group.name = data['name']

            # permissions
            permissions = 0
            for perm in data['permissions']:
                permissions |= int(perm)
            if permissions != group.permissions:
                changed_permissions = True
                group.permissions = permissions

            #: forum privileges
            for key, value in request.POST.iteritems():
                if key.startswith('forum_privileges-'):
                    forum_id = key.split('-', 1)[1]
                    privilege = Privilege.query.filter(and_(
                        privilege_table.c.forum_id==forum_id,
                        privilege_table.c.user_id==None,
                        privilege_table.c.group_id==group.id
                    )).first()
                    if not privilege:
                        privilege = Privilege(
                            group=group,
                            forum=Forum.query.get(int(forum_id)))
                        dbsession.save(privilege)

                    privilege.bits = join_flags(*value)
                    dbsession.flush()

            # save changes to the database
            group.save()
            dbsession.commit()

            # clear permission cache of users if needed
            if changed_permissions:
                c = user_group_table.c
                keys = ['user_permissions/%s' % row[0] for row in
                    dbsession.execute(
                        select([c.user_id]).where(c.group_id == group.id)
                    ).fetchall()
                ]
                cache.delete_many(*keys)

            flash(u'Die Gruppe „%s“ wurde erfolgreich %s'
                  % (escape(group.name), new and 'erstellt' or 'editiert'),
                  True)
    else:
        form = EditGroupForm(initial=not new and {
            'name': group.name,
            'permissions': filter(lambda p: p & group.permissions, PERMISSION_NAMES.keys())
        } or {})
        _add_choices(form)

    # collect forum privileges
    forum_privileges = []
    forums = Forum.query.all()
    for forum in forums:
        privilege = Privilege.query.filter(and_(
            privilege_table.c.forum_id==forum.id,
            privilege_table.c.group_id==group.id,
        )).first()

        forum_privileges.append((
            forum.id,
            forum.name,
            list(split_flags(privilege and privilege.bits or None))
        ))

    return {
        'group_forum_privileges': forum_privileges,
        'forum_privileges': PRIVILEGES_DETAILS,
        'group_name': '' or not new and group.name,
        'form': form,
        'is_new': new,
    }


@require_permission('event_edit')
@templated('admin/events.html')
def events(request, show_all=False):
    if show_all:
        objects = Event.objects.all()
    else:
        objects = Event.objects.filter(date__gt=date.today())
    sortable = Sortable(objects, request.GET, '-date')
    return {
        'table': sortable,
        'events': sortable.get_objects(),
        'show_all': show_all,
    }


@require_permission('event_edit')
@templated('admin/event_edit.html')
def event_edit(request, id=None):
    mode = (id is None) and 'new' or 'edit'

    if request.method == 'POST':
        form = EditEventForm(request.POST)
        if form.is_valid():
            if id is not None:
                try:
                    event = Event.objects.get(id=id)
                except Event.DoesNotExist:
                    raise PageNotFound
            else:
                event = Event()
            data = form.cleaned_data
            event.name = data['name']
            event.date = data['date']
            event.time = data['time']
            event.description = data['description']
            event.author = request.user
            event.location = data['location']
            event.location_town = data['location_town']
            if data['location_lat'] and data['location_long']:
                event.location_lat = data['location_lat']
                event.location_long = data['location_long']
            event.save()
            flash(u'Die Veranstaltung wurde gespeichert.', True)
            return HttpResponseRedirect(event.get_absolute_url())
    else:
        if id is not None:
            try:
                event = Event.objects.get(id=id)
            except Event.DoesNotExist:
                raise PageNotFound
            form = EditEventForm({
                'name': event.name,
                'date': event.date,
                'time': event.time,
                'description': event.description,
                'location_town': event.location_town,
                'location': event.location,
                'location_lat': event.location_lat,
                'location_long': event.location_long,
            });
        else:
            form = EditEventForm()
            event = None
    return {
        'form': form,
        'mode': mode,
        'event': event,
    }


@require_permission('event_edit')
@templated('admin/event_delete.html')
def event_delete(request, id):
    try:
        event = Event.objects.get(id=id)
    except Event.DoesNotExist:
        raise PageNotFound
    if request.method == 'POST':
        if request.POST['confirm']:
            event.delete()
            flash(u'Die Veranstaltung „%s“ wurde gelöscht.'
                  % escape(event.name), True)
        return HttpResponseRedirect(href('admin', 'events'))
    else:
        return {'event': event}


@require_permission('markup_css_edit')
@templated('admin/styles.html')
def styles(request):
    key = 'markup_styles'
    if request.method == 'POST':
        form = EditStyleForm(request.POST)
        if form.is_valid():
            storage[key] = form.data['styles']
            flash(u'Das Stylesheet wurde erfolgreich gespeichert', True)
    else:
        form = EditStyleForm(initial={'styles': storage.get(key, u'')})
    return {
        'form': form
    }
