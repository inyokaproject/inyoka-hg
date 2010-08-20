#-*- coding: utf-8 -*-
"""
    inyoka.admin.views
    ~~~~~~~~~~~~~~~~~~~

    This module holds the admin views.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import os
import pytz
import time
from os import path
from PIL import Image
from StringIO import StringIO
from sqlalchemy import and_, select
from datetime import date, time as dt_time
from django.db.models import Max
from django.forms.models import model_to_dict
from django.forms.util import ErrorList
from inyoka.conf import settings
from inyoka.utils.text import slugify
from inyoka.utils.http import templated
from inyoka.utils.cache import cache
from inyoka.utils.urls import url_for, href, global_not_found
from inyoka.utils.flashing import flash
from inyoka.utils.templating import render_template
from inyoka.utils.html import escape
from inyoka.utils.http import HttpResponseRedirect, PageNotFound
from inyoka.utils.sortable import Sortable
from inyoka.utils.storage import storage
from inyoka.utils.mail import send_mail
from inyoka.utils.pagination import Pagination
from inyoka.utils.database import session as dbsession
from inyoka.utils.dates import datetime_to_timezone, get_user_timezone, \
        date_time_to_datetime
from inyoka.utils.mongolog import get_mdb_database
from inyoka.admin.forms import EditStaticPageForm, EditArticleForm, \
     EditBlogForm, EditCategoryForm, EditFileForm, ConfigurationForm, \
     EditUserForm, EditEventForm, EditForumForm, EditGroupForm, \
     CreateUserForm, EditStyleForm, CreateGroupForm, UserMailForm, \
     EditPublicArticleForm
from inyoka.portal.models import StaticPage, Event, StaticFile
from inyoka.portal.user import User, Group, PERMISSION_NAMES, send_activation_mail
from inyoka.portal.utils import require_permission
from inyoka.planet.models import Blog
from inyoka.ikhaya.models import Article, Suggestion, Category
from inyoka.forum.acl import REVERSED_PRIVILEGES_BITS, split_bits, \
    PRIVILEGES_DETAILS
from inyoka.forum.models import Forum, Privilege, WelcomeMessage
from inyoka.forum.compat import SAUser, user_group_table
from inyoka.wiki.parser import parse, RenderContext

tmp = dict(PRIVILEGES_DETAILS)
PRIVILEGE_DICT = dict((bits, tmp[key]) for  bits, key in
                    REVERSED_PRIVILEGES_BITS.iteritems())
del tmp


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
    keys = ['max_avatar_width', 'max_avatar_height', 'max_avatar_size',
            'max_signature_length', 'max_signature_lines', 'get_ubuntu_link',
            'license_note', 'get_ubuntu_description', 'blocked_hosts',
            'wiki_newpage_template', 'wiki_newpage_root', 'team_icon_height',
            'team_icon_width']

    team_icon = storage['team_icon']

    if request.method == 'POST':
        form = ConfigurationForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            for k in keys:
                storage[k] = data[k]

            if data['global_message'] != storage['global_message']:
                storage['global_message'] = data['global_message']
                storage['global_message_time'] = time.time()

            if data['team_icon']:
                img_data = data['team_icon'].read()
                icon = Image.open(StringIO(img_data))
                fn = 'portal/global_team_icon.%s' % icon.format.lower()
                imgp = path.join(settings.MEDIA_ROOT, fn)

                if path.exists(imgp):
                    os.remove(imgp)

                f = open(imgp, 'wb')
                try:
                    f.write(img_data)
                finally:
                    f.close()

                storage['team_icon'] = fn

            if data['license_note']:
                context = RenderContext(request, simplified=True)
                node = parse(data['license_note'])
                storage['license_note_rendered'] = node.render(context, 'html')

            flash(u'Die Einstellungen wurden gespeichert.', True)
    else:
        form = ConfigurationForm(initial=storage.get_many(keys +
                                                ['global_message']))
    return {
        'form': form,
        'team_icon_url': team_icon and href('media', team_icon) or None
    }


@require_permission('static_page_edit')
@templated('admin/pages.html')
def pages(request):
    sortable = Sortable(StaticPage.objects.all(), request.GET, '-key',
        columns=['key', 'title'])
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
                        url_for(page), escape(page.title)), True)
            else:
                page.key = key
                page.title = title
                page.content = content
                flash(u'Die Seite „<a href="%s">%s</a>“ '
                      u'wurde erfolgreich editiert.' % (
                        url_for(page), escape(page.title)), True)
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
                  % escape(page.title), True)
    else:
        flash(render_template('admin/pages_delete.html', {
                'page': page}))
    return HttpResponseRedirect(href('admin', 'pages'))


@require_permission('static_file_edit')
@templated('admin/files.html')
def files(request):
    sortable = Sortable(StaticFile.objects.all(), request.GET, 'identifier',
        columns=['identifier', 'is_ikhaya_icon'])
    return {
        'table': sortable,
        'files': sortable.get_objects(),
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
                file.file.save(data['file'].name, data['file'])
                file.identifier = data['file'].name
            file.is_ikhaya_icon = data['is_ikhaya_icon']
            file.save()
            flash(u'Die statische Datei wurde %s.'
                  % (new and u'erstellt' or u'geändert'), True)
            if new:
                return HttpResponseRedirect(url_for(file, 'edit'))
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


@require_permission('static_file_edit')
def file_delete(request, file):
    file = StaticFile.objects.get(identifier=file)
    if request.method == 'POST':
        if 'cancel' in request.POST:
            flash(u'Löschen abgebrochen')
        else:
            file.delete()
            flash(u'Die Datei „%s” wurde erfolgreich gelöscht'
                  % escape(file.identifier), True)
    else:
        flash(render_template('admin/files_delete.html', {'file': file}))
    return HttpResponseRedirect(href('admin', 'files'))


@require_permission('blog_edit')
@templated('admin/planet.html')
def planet(request):
    q = Blog.objects.annotate(latest_update=Max('entry__pub_date'))
    sortable = Sortable(q, request.GET, '-latest_update',
                        columns=['name', 'latest_update'])
    return {
        'table': sortable,
        'blogs': sortable.get_objects(),
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
            for k in ('name', 'description', 'blog_url', 'feed_url', 'active'):
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
                        url_for(blog), escape(blog.name)), True)
            else:
                flash(u'Der Blog „<a href="%s">%s</a>“ '
                      u'wurde erfolgreich editiert.' % (
                        url_for(blog), escape(blog.name)), True)
            return HttpResponseRedirect(href('admin', 'planet'))
    else:
        if not new:
            form = EditBlogForm(initial=model_to_dict(blog))
        else:
            form = EditBlogForm()

    return {
        'form': form,
        'blog': blog
    }


@require_permission('article_read', 'category_edit', 'event_edit')
@templated('admin/ikhaya.html')
def ikhaya(request):
    return {}


@require_permission('article_read', 'article_edit')
@templated('admin/ikhaya_articles.html')
def ikhaya_articles(request, page=1):
    sorted = request.GET.get('order', None) is not None
    if not sorted:
        objects = Article.objects.order_by('public', '-updated').select_related()
    else:
        objects = Article.objects.all()

    sortable = Sortable(objects, request.GET, '-updated',
        columns=['subject', 'portal_user.username', 'ikhaya_category.name',
                 'updated'])
    pagination = Pagination(request,
        sorted and sortable.get_objects() or objects,
        page, 25, href('admin', 'ikhaya', 'articles'))

    return {
        'table': sortable,
        'articles': list(pagination.objects),
        'pagination': pagination
    }


@require_permission('article_edit')
@templated('admin/ikhaya_article_edit.html')
def ikhaya_article_edit(request, article_id=None, suggestion_id=None):
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

    if article_id:
        article = Article.objects.get(id=int(article_id))
    else:
        article = None

    if request.method == 'POST':
        if article and article.public:
            form = EditPublicArticleForm(request.POST)
        else:
            form = EditArticleForm(request.POST)
        if 'send' in request.POST:
            _add_field_choices()
            if form.is_valid():
                data = form.cleaned_data
                data['author'] = data['author'] or request.user
                if not data['updated']:
                    data['updated'] = data['pub_date']
                if data['updated']:
                    data['updated'] = get_user_timezone() \
                        .localize(data['updated']) \
                        .astimezone(pytz.utc).replace(tzinfo=None)
                if data['pub_date']:
                    dt = get_user_timezone().localize(data['pub_date']) \
                        .astimezone(pytz.utc).replace(tzinfo=None)
                    data['pub_date'], data['pub_time'] = dt.date(), dt.time()
                checksum = data.pop('checksum')

                if not data.get('icon_id'):
                    data['icon_id'] = None
                if not article:
                    article = Article(**data)
                    article.save()
                    if suggestion_id:
                        Suggestion.objects.delete([suggestion_id])
                    flash(u'Der Artikel „%s“ wurde erstellt.'
                          % escape(article.subject), True)
                    return HttpResponseRedirect(url_for(article, 'edit'))
                else:
                    changed = False
                    db_checksum = article.checksum
                    for k in data:
                        if article.__getattribute__(k) != data[k] \
                           and data[k] not in (None, ''):
                            article.__setattr__(k, data[k])
                            changed = True
                    if changed:
                        if db_checksum == checksum:
                            article.save()
                            flash(u'Der Artikel „%s“ wurde gespeichert.'
                                  % escape(article.subject), True)
                            return HttpResponseRedirect(url_for(article))
                        else:
                            form.errors['__all__'] = ErrorList(
                                form.errors.get('__all__', []) + [
                                    u'Der Artikel wurde seit Beginn des '
                                    u'Bearbeitens verändert!'
                                ])
                    else:
                        flash(u'Der Artikel „%s“ wurde nicht verändert'
                              % escape(article.subject))
                return HttpResponseRedirect(article.get_absolute_url('edit'))
        elif 'preview' in request.POST:
            ctx = RenderContext(request)
            preview = parse('%s\n\n%s' % (request.POST.get('intro', ''),
                            request.POST.get('text'))).render(ctx, 'html')
    else:
        if article_id:
            initial = {
                'subject': article.subject,
                'intro': article.intro,
                'text': article.text,
                'author': article.author,
                'category_id': article.category.id,
                'icon_id': article.icon and article.icon.id or None,
                'pub_date': datetime_to_timezone(article.pub_datetime).replace(tzinfo=None),
                'public': article.public,
                'slug': article.slug,
                'comments_enabled': article.comments_enabled,
                'checksum': article.checksum,
            }
            if article.updated != article.pub_datetime:
                initial['updated'] = datetime_to_timezone(article.updated).replace(tzinfo=None)
            if article.public:
                form = EditPublicArticleForm(initial=initial)
            else:
                form = EditArticleForm(initial=initial)
        elif suggestion_id:
            suggestion = Suggestion.objects.get(id=suggestion_id)
            form = EditArticleForm(initial={
                'subject': suggestion.title,
                'text':    suggestion.text,
                'intro':   suggestion.intro,
                'author':  suggestion.author,
            })
        else:
            form = EditArticleForm()
        _add_field_choices()

    return {
        'form': form,
        'article': article,
        'preview': preview,
    }


@require_permission('article_edit')
def ikhaya_article_delete(request, article_id):
    article = Article.objects.get(id=int(article_id))
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
                  % escape(article.subject), True)
    else:
        flash(render_template('admin/ikhaya_article_delete.html',
              {'article': article}))
    return HttpResponseRedirect(href('admin', 'ikhaya', 'articles'))


@require_permission('category_edit')
@templated('admin/ikhaya_categories.html')
def ikhaya_categories(request):
    sortable = Sortable(Category.objects.all(), request.GET, '-name',
        columns=['name'])
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


@require_permission('forum_edit')
@templated('admin/forums.html')
def forums(request):
    sortable = Sortable(Forum.query, request.GET, 'name',
        sqlalchemy=True, sa_column=Forum.name,
        columns=['name', 'parent_id', 'position'])
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
            query = Forum.query.filter(Forum.id!=id)
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
            if Forum.query.filter(and_(Forum.slug==slug, Forum.id!=id)).first():
                form.errors['slug'] = ErrorList(
                    [u'Bitte einen anderen Slug angeben, „%s“ ist schon '
                     u'vergeben.' % escape(slug)])
            if int(data['parent']) != -1:
                parent = Forum.query.get(int(data['parent']))
                if not parent:
                    form.errors['parent'] = ErrorList(
                        [u'Forum %s existiert nicht'
                         % escape(data['parent'])])

        if form.is_valid():
            if not id:
                forum = Forum()
            forum.name = data['name']
            forum.position = data['position']
            old_slug = forum.slug
            forum.slug = slug
            forum.description = data['description']
            if int(data['parent']) != -1:
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

            forum.newtopic_default_text = data.get('newtopic_default_text', None)
            forum.force_version = data['force_version']

            if not form.errors and not errors:
                dbsession.commit()
                keys = ['forum/index'] + ['forum/forum/' + f.slug
                                          for f in forum.parents]
                if old_slug is not None:
                    keys.append('forum/forum/' + old_slug)
                cache.delete_many(*keys)
                flash(u'Das Forum „%s“ wurde erfolgreich %s' % (
                      escape(forum.name), not id and 'angelegt' or 'editiert'), True)
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
                'welcome_msg_text': welcome_msg and welcome_msg.text or u'',
                'force_version': forum.force_version,
                'count_posts': forum.user_count_posts,
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
            try:
                user = User.objects.get(name)
            except User.DoesNotExist, e:
                # fallback to email
                if '@' in name:
                    user = User.objects.get(email__iexact=name)
                else:
                    raise e
        except User.DoesNotExist:
            flash(u'Der Benutzer „%s“ existiert nicht.'
                  % escape(name))
        else:
            return HttpResponseRedirect(user.get_absolute_url('admin'))
    return {}


@require_permission('user_edit')
@templated('admin/userlist.html')
def users_with_special_rights(request):
    query = SAUser.query.filter(Privilege.user_id == SAUser.id) \
                        .filter(Privilege.user_id != None) \
                        .group_by(SAUser.id).order_by(SAUser.username)
    users = list(query)
    return {
        'users': users,
        'count': len(users),
    }


@require_permission('user_edit')
@templated('admin/user_edit.html')
def user_edit(request, username):
    #: check if the user exists
    try:
        if '@' in username:
            user = User.objects.get(email__iexact=username)
        else:
            user = User.objects.get(username)
    except User.DoesNotExist:
        raise PageNotFound
    if username != user.urlsafe_username:
        return HttpResponseRedirect(user.get_absolute_url('admin'))

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
                    User.objects.get(data['username'])
                except User.DoesNotExist:
                    user.username = data['username']
                else:
                    form.errors['username'] = ErrorList(
                        [u'Ein Benutzer mit diesem Namen existiert bereits'])

        if form.is_valid():
            #: set the user attributes, avatar and forum privileges
            for key in ('status', 'date_joined', 'banned_until',
                        'website', 'interests', 'location', 'jabber', 'icq',
                        'msn', 'aim', 'yim', 'signature', 'coordinates_long',
                        'coordinates_lat', 'gpgkey', 'email', 'skype', 'sip',
                        'wengophone', 'member_title', 'launchpad'):
                setattr(user, key, data[key])
            if data['delete_avatar']:
                user.delete_avatar()

            if data['avatar']:
                avatar_resized = user.save_avatar(data['avatar'])
                if avatar_resized:
                    ava_mh, ava_mw = storage.get_many(('max_avatar_height',
                        'max_avatar_width')).itervalues()
                    flash(u'Der von dir hochgeladene Avatar wurde auf '
                          u'%sx%s Pixel skaliert. Dadurch könnten '
                          u'Qualitätseinbußen aufgetreten sein. '
                          u'Bitte beachte dies.'
                          % (ava_mh, ava_mw))

            if data['new_password']:
                user.set_password(data['new_password'])

            # permissions
            permissions = 0
            for perm in checked_perms:
                permissions |= perm
            user._permissions = permissions

            #: forum privileges
            privileges = Privilege.query
            for key, value in request.POST.iteritems():
                if key.startswith('forum_privileges_'):
                    positive = 0
                    negative = 0
                    for bit in value.split(','):
                        try:
                            bit = int(bit)
                        except ValueError:
                            continue
                        if bit > 0:
                            positive |= bit
                        else:
                            negative |= bit * -1

                    forum_id = key.split('_')[2]
                    privilege = privileges.filter(and_(
                        Privilege.forum_id==forum_id,
                        Privilege.group_id==None,
                        Privilege.user_id==user.id
                    )).first()
                    if privilege is None and (positive or negative):
                        privilege = Privilege(
                            user=user,
                            forum=Forum.query.get(int(forum_id))
                        )
                    if negative or positive:
                        privilege.positive = positive
                        privilege.negative = negative
                    elif privilege is not None:
                        dbsession.delete(privilege)

            # group editing
            groups_joined = [groups[gn] for gn in
                             request.POST.getlist('user_groups_joined')]
            groups_not_joined = [groups[gn] for gn in
                                request.POST.getlist('user_groups_not_joined')]
            user.groups.remove(*groups_not_joined)
            user.groups.add(*groups_joined)

            if user._primary_group:
                oprimary = user._primary_group.name
            else:
                oprimary = ""

            primary = None
            if oprimary != data['primary_group']:
                try:
                    primary = Group.objects.get(name=data['primary_group'])
                except Group.DoesNotExist:
                    primary = None
            user._primary_group = primary

            # save the user object back to the database as well as other
            # database changes
            dbsession.commit()
            user.save()
            cache.delete('user_permissions/%s' % user.id)

            flash(u'Das Benutzerprofil von "%s" wurde erfolgreich aktualisiert!'
                  % escape(user.username), True)
            # redirect to the new username if given
            if user.username != username:
                return HttpResponseRedirect(href('admin', 'users', 'edit', user.username))
        else:
            flash(u'Es sind Fehler aufgetreten, bitte behebe sie!', False)
    else:
        initial = model_to_dict(user)
        if initial['_primary_group']:
            initial.update({
                'primary_group': Group.objects.get(id=initial['_primary_group']).name
            })
        form = EditUserForm(initial=initial)

    # collect forum privileges
    forum_privileges = []
    forums = Forum.query.all()
    for forum in forums:
        privilege = Privilege.query.filter(and_(
            Privilege.forum_id==forum.id,
            Privilege.user_id==user.id
        )).first()

        forum_privileges.append((
            forum.id,
            forum.name,
            list(split_bits(privilege and privilege.positive or None)),
            list(split_bits(privilege and privilege.negative or None))
        ))

    groups_joined = groups_joined or user.groups.all()
    groups_not_joined = groups_not_joined or \
                        [x for x in groups.itervalues() if not x in groups_joined]

    storage_data = storage.get_many(('max_avatar_height', 'max_avatar_width'))

    permissions = []

    groups = user.groups.all()
    for id, name in PERMISSION_NAMES.iteritems():
        derived = filter(lambda g: id & g.permissions, groups)
        if request.method == 'POST':
            checked = id in checked_perms
        else:
            checked = id & user._permissions
        permissions.append((id, name, checked, derived))

    forum_privileges = sorted(forum_privileges, lambda x, y: cmp(x[1], y[1]))

    if user.status > 0:
        activation_link = None
    else:
        activation_link = user.get_absolute_url('activate')

    return {
        'user': user,
        'form': form,
        'forum_privileges': PRIVILEGE_DICT,
        'user_forum_privileges': forum_privileges,
        'joined_groups': [g.name for g in groups_joined],
        'not_joined_groups': [g.name for g in groups_not_joined],
        'avatar_height': storage_data['max_avatar_height'],
        'avatar_width': storage_data['max_avatar_width'],
        'permissions': sorted(permissions, key=lambda p: p[1]),
        'activation_link': activation_link,
    }


@require_permission('user_edit')
@templated('admin/user_new.html')
def user_new(request):
    if request.method == 'POST':
        form = CreateUserForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            User.objects.register_user(
                username=data['username'],
                email=data['email'],
                password=data['password'],
                send_mail=data['authenticate'])
            flash(u'Der Benutzer „%s“ wurde erfolgreich erstellt. '
                  u'Du kannst nun weitere Details bearbeiten.'
                  % escape(data['username']), True)
            return HttpResponseRedirect(href('admin', 'users', 'edit',
                                             escape(data['username'])))
        else:
            flash(u'Es sind Probleme aufgetreten, bitte behebe sie!', False)
    else:
        form = CreateUserForm()
    return {
        'form': form
    }

@require_permission('user_edit')
def resend_activation_mail(request):
    user = User.objects.get(request.GET.get('user'))
    if user.status != 0:
        flash(u'Der Benutzer ist schon aktiviert.')
    else:
        send_activation_mail(user)
        flash(u'Die Aktivierungsmail wurde erneut versandt.', True)
    return HttpResponseRedirect(request.GET.get('next') or href('admin', 'users'))


@require_permission('user_edit')
@templated('admin/user_mail.html')
def user_mail(request, username):
    try:
        if '@' in username:
            user = User.objects.get(email__iexact=username)
        else:
            user = User.objects.get(username)
    except User.DoesNotExist:
        raise PageNotFound
    if request.method == 'POST':
        form = UserMailForm(request.POST)
        if form.is_valid():
            text = form.cleaned_data['text']
            message = render_template('mails/formmailer_template.txt', {
                'user': user,
                'text': text,
                'from': request.user.username,
            })
            #try:
            send_mail(
                'ubuntuusers.de - Nachricht von %s' % request.user.username,
                message,
                settings.INYOKA_SYSTEM_USER_EMAIL,
                [user.email])
            #except: # don't know which exception is thrown
            #    flash(u'Die Mail konnte nicht verschickt werden.')
            #    return HttpResponseRedirect(href('admin', 'users', 'mail',
            #                                 escape(username)))
            flash(u'Die Mail an „%s“ wurde erfolgreich verschickt.'
                  % escape(username), True)
            return HttpResponseRedirect(request.GET.get('next') or href('admin', 'users'))
        else:
            flash(u'Es sind Probleme aufgetreten, bitte behebe sie!', False)
    else:
        form = UserMailForm()
    return {
        'form': form,
        'user': user,
    }

@require_permission('group_edit')
@templated('admin/groups.html')
def groups(request):
    if request.method == 'POST':
        name = request.POST.get('group')
        try:
            Group.objects.get(name=name)
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
        form_class = CreateGroupForm
    else:
        try:
            group = Group.objects.get(name=name)
        except Group.DoesNotExist:
            flash(u'Die Gruppe „%s“ existiert nicht.'
                  % escape(name), False)
            return HttpResponseRedirect(href('admin', 'groups'))
        form_class = EditGroupForm

    icon_mh, icon_mw = storage.get_many(('team_icon_height',
                                         'team_icon_width')).itervalues()

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES)
        _add_choices(form)
        if form.is_valid():
            data = form.cleaned_data
            group.name = data['name']
            group.is_public = data['is_public']

            if data['delete_icon']:
                group.delete_icon()

            if data['icon'] and not data['import_icon_from_global']:
                icon_resized = group.save_icon(data['icon'])
                if icon_resized:
                    flash(u'Das von dir hochgeladene Icon wurde auf '
                          u'%sx%s Pixel skaliert, dadurch können '
                          u'Qualitätseinbußen auftreten. Bitte beachte dies.'
                          % (icon_mh, icon_mw))

            if data['import_icon_from_global']:
                group.delete_icon()

                icon_path = 'portal/team_icons/team_%s.%s' % (group.name,
                            storage['team_icon'].split('.')[-1])
                if storage['team_icon']:
                    global_icon = open(path.join(settings.MEDIA_ROOT, storage['team_icon']))
                    icon_fo = open(path.join(settings.MEDIA_ROOT, icon_path), 'w')
                    try:
                        icon_fo.write(global_icon.read())
                        group.icon = icon_path
                    finally:
                        global_icon.close()
                        icon_fo.close()
                else:
                    flash(u'Es wurde noch kein globales Team-Icon definiert', False)

            # permissions
            permissions = 0
            for perm in data['permissions']:
                permissions |= int(perm)
            if permissions != group.permissions:
                changed_permissions = True
                group.permissions = permissions

            group.save()

            #: forum privileges
            for key, value in request.POST.iteritems():
                if key.startswith('forum_privileges_'):
                    negative = 0
                    positive = 0
                    for bit in value.split(','):
                        try:
                            bit = int(bit)
                        except ValueError:
                            continue
                        if bit > 0:
                            positive |= bit
                        else:
                            negative |= bit

                    forum_id = key.split('_')[2]
                    privilege = Privilege.query.filter(and_(
                        Privilege.forum_id==forum_id,
                        Privilege.user_id==None,
                        Privilege.group_id==group.id
                    )).first()
                    if privilege is None and (positive or negative):
                        privilege = Privilege(
                            group=group,
                            forum=Forum.query.get(int(forum_id)))
                    if negative or positive:
                        privilege.positive = positive
                        privilege.negative = negative
                    elif privilege is not None:
                        dbsession.delete(privilege)

            # save changes to the database
            dbsession.commit()
            group.save()

            # clear permission cache of users if needed
            if changed_permissions:
                c = user_group_table.c
                keys = ['user_permissions/%s' % row[0] for row in
                    dbsession.execute(
                        select([c.user_id]).where(c.group_id == group.id)
                    ).fetchall()
                ]
                cache.delete_many(*keys)

            flash(u'Die Gruppe „<a href="%s">%s</a>“ wurde erfolgreich %s'
                  % (href('admin', 'groups', escape(group.name)),
                     escape(group.name), new and 'erstellt' or 'editiert'),
                  True)
            if new:
                return HttpResponseRedirect(group.get_absolute_url('edit'))
    else:
        form = form_class(initial=not new and {
            'name': group.name,
            'permissions': filter(lambda p: p & group.permissions, PERMISSION_NAMES.keys()),
            'is_public': group.is_public,
        } or {
            'is_public': True,
        })
        _add_choices(form)

    # collect forum privileges
    forum_privileges = []
    forums = Forum.query.all()
    for forum in forums:
        privilege = Privilege.query.filter(and_(
            Privilege.forum_id==forum.id,
            Privilege.group_id==group.id,
        )).first()

        forum_privileges.append((
            forum.id,
            forum.name,
            list(split_bits(privilege and privilege.positive or None)),
            list(split_bits(privilege and privilege.negative or None))
        ))

    return {
        'group_forum_privileges': forum_privileges,
        'forum_privileges': PRIVILEGE_DICT,
        'group_name': '' or not new and group.name,
        'form': form,
        'is_new': new,
        'group': group,
        'team_icon_height': icon_mh,
        'team_icon_width': icon_mw,
    }


@require_permission('event_edit')
@templated('admin/events.html')
def events(request, show_all=False):
    if show_all:
        objects = Event.objects.all()
    else:
        objects = Event.objects.filter(date__gt=date.today())
    sortable = Sortable(objects, request.GET, '-date',
        columns=['name', 'date'])
    return {
        'table': sortable,
        'events': sortable.get_objects(),
        'show_all': show_all,
    }


@require_permission('event_edit')
@templated('admin/event_edit.html')
def event_edit(request, id=None):
    mode = (id is None) and 'new' or 'edit'
    base_event = None
    if request.GET.get('copy_from'):
        try:
            base_event = Event.objects.get(id=int(request.GET['copy_from']))
        except Event.DoesNotExist:
            flash(u'Das Event mit der ID %d existiert nicht und kann '
                  u'daher nicht als Basis des Kopiervorgangs benutzt werden',
                  False)

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
            convert = (lambda v: get_user_timezone().localize(v) \
                                .astimezone(pytz.utc).replace(tzinfo=None))
            data = form.cleaned_data
            event.name = data['name']
            if data['date'] and data['time']:
                d = convert(date_time_to_datetime(
                    data['date'],
                    data['time'] or dt_time(0)
                ))
                event.date = d.date()
                event.time = d.time()
            else:
                event.date = data['date']
                event.time = None
            if data['duration']:
                event.duration = convert(data['duration'])
            event.description = data['description']
            event.author = request.user
            event.location = data['location']
            event.location_town = data['location_town']
            if data['location_lat'] and data['location_long']:
                event.location_lat = data['location_lat']
                event.location_long = data['location_long']
            event.save()
            flash(u'Die Veranstaltung wurde gespeichert.', True)
            return HttpResponseRedirect(url_for(event))
        else:
            event = None
    else:
        if id is not None:
            try:
                event = Event.objects.get(id=id)
            except Event.DoesNotExist:
                raise PageNotFound()
        elif base_event:
            event = base_event
        else:
            event = None

        if event is not None:
            if event.date and event.time:
                dt = datetime_to_timezone(date_time_to_datetime(
                    event.date, event.time or dt_time(0)))
                dt_date = dt.date()
                time_ = dt.time()
            else:
                dt_date = event.date
                time_ = None
            form = EditEventForm({
                'name': event.name,
                'date': dt_date,
                'time': time_,
                'duration': datetime_to_timezone(event.duration),
                'description': event.description,
                'location_town': event.location_town,
                'location': event.location,
                'location_lat': event.location_lat,
                'location_long': event.location_long,
            })
        else:
            form = EditEventForm()

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
        if 'confirm' in request.POST:
            event.delete()
            flash(u'Die Veranstaltung „%s“ wurde gelöscht.'
                  % escape(event.name), True)
        else:
            flash(u'Löschen der Veranstaltung „%s“ wurde abgebrochen'
                  % escape(event.name))
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


@require_permission('manage_stats')
@templated('admin/monitoring.html')
def monitoring(request):
    from pymongo import DESCENDING
    database = get_mdb_database(True)
    collection = database['errors']

    if 'close' in request.GET:
        hash = request.GET.get('close')
        if collection.find({'hash': hash}).count():
            collection.update({'hash': hash}, {'$set': {'status': 'close'}})
            return HttpResponseRedirect(href('admin', 'monitoring'))

    all_errors = collection.find({'status': {'$in': ['new', 'open', 'reopen']}}) \
                           .sort('created', DESCENDING)
    error_count = collection.count()
    closed = collection.find({'status': 'close'}).count()
    reopened = collection.find({'status': 'reopen'}).count()

    stats = {
        'closed': closed,
        'open': error_count - closed - reopened,
        'reopened': reopened
    }
    return {
        'count': error_count,
        'stats': stats,
        'errors': all_errors
    }
