#-*- coding: utf-8 -*-
"""
    inyoka.portal.admin
    ~~~~~~~~~~~~~~~~~~~

    This module holds the admin views.

    :copyright: 2008 by Christopher Grebs, Benjamin Wiegand.
    :license: GNU GPL.
"""
from copy import copy as ccopy
from datetime import datetime
from django.http import HttpResponse, HttpResponseRedirect
from django.newforms.models import model_to_dict
from inyoka.utils import slugify
from inyoka.utils.http import templated
from inyoka.utils.urls import url_for, href
from inyoka.utils.flashing import flash, DEFAULT_FLASH_BUTTONS
from inyoka.utils.html import escape, cleanup_html
from inyoka.utils.sortable import Sortable
from inyoka.utils.storage import storage
from inyoka.utils.pagination import Pagination
from inyoka.admin.forms import EditStaticPageForm, EditArticleForm, \
                               EditBlogForm, EditCategoryForm, EditIconForm, \
                               ConfigurationForm, EditUserForm, EditDateForm, \
                               EditForumForm, EditGroupForm
from inyoka.portal.models import StaticPage, Event
from inyoka.portal.user import User, Group
from inyoka.portal.utils import require_manager
from inyoka.planet.models import Blog
from inyoka.ikhaya.models import Article, Suggestion, Category, Icon
from inyoka.forum.acl import PRIVILEGES_DETAILS, PRIVILEGES
from inyoka.forum.models import Forum, Privilege


IKHAYA_ARTICLE_DELETE_BUTTONS = [
    {'type': 'submit', 'class': 'message-yes', 'name': 'message-yes',
     'value': 'Löschen'},
    {'type': 'submit', 'class': 'message-depublicate',
     'name': 'message-depublicate', 'value': 'Veröffentlichung aufheben'},
    {'type': 'submit', 'class': 'message-no', 'name': 'message-no',
     'value': 'Abbrechen'}
]


@require_manager
@templated('admin/index.html')
def index(request):
    return {}


@require_manager
@templated('admin/configuration.html')
def config(request):
    if request.method == 'POST':
        form = ConfigurationForm(request.POST)
        if form.is_valid():
            html = cleanup_html(form.cleaned_data['global_message'])
            storage['global_message'] = html
            flash(u'Die Einstellungen wurden gespeichert.', True)
            return HttpResponseRedirect(href('admin', 'config'))
    else:
        form = ConfigurationForm(initial=storage.get_many(['global_message']))
    return {
        'form': form
    }


@require_manager
@templated('admin/pages.html')
def pages(request):
    sortable = Sortable(StaticPage.objects.all(), request.GET, '-key')
    return {
        'table': sortable,
        'pages': sortable.get_objects(),
    }


@require_manager
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


@require_manager
def pages_delete(request, page_key):
    if not page_key:
        flash(u'Es wurde keine Seite zum löschen ausgewählt.')
    page = StaticPage.objects.get(key=page_key)
    if request.method == 'POST':
        if 'message-yes' in request.POST:
            page.delete()
            flash(u'Die Seite „%s“ wurde erfolgreich gelöscht'
                  % escape(page.title))
    else:
        flash(u'Möchtest du die Seite „%s“ wirklich löschen?'
              % escape(page.title), dialog=True,
              dialog_url=href('admin', 'pages', 'delete', page_key))
    return HttpResponseRedirect(href('admin', 'pages'))


@require_manager
@templated('admin/planet.html')
def planet(request):
    return {
        'blogs': Blog.objects.all(),
    }


@require_manager
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


@require_manager
@templated('admin/ikhaya.html')
def ikhaya(request):
    return {}


@require_manager
@templated('admin/ikhaya_articles.html')
def ikhaya_articles(request, page=1):
    sortable = Sortable(Article.objects.all(), request.GET, '-pub_date')
    pagination = Pagination(request, sortable.get_objects(), page, 25)
    return {
        'table': sortable,
        'articles': list(pagination.get_objects()),
        'pagination': pagination.generate()
    }


@require_manager
@templated('admin/ikhaya_article_edit.html')
def ikhaya_article_edit(request, article=None, suggestion_id=None):
    """
    Display an interface to let the user create or edit an article.
    If `suggestion_id` is given, the new ikhaya article is based on a special
    article suggestion made by a user. After saving it, the suggestion will be
    deleted automatically.
    """
    def _add_field_choices():
        categories = [(c.id, c.name) for c in Category.objects.all()]
        icons = [(i.id, i.identifier) for i in Icon.objects.all()]
        form.fields['icon'].choices = icons
        form.fields['category'].choices = categories

    if article:
        article = Article.objects.get(slug=article)

    if request.method == 'POST':
        form = EditArticleForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            data = form.cleaned_data
            data['category_id'] = data.pop('category')
            data['icon_id'] = data.pop('icon')
            if not article:
                article = Article(**form.cleaned_data)
                article.save()
                if suggestion_id:
                    Suggestion.objects.delete([suggestion_id])
                flash('Der Artikel wurde erstellt.', True)
            else:
                changed = False
                for k in data:
                    if article.__getattribute__(k) != data[k]:
                        article.__setattr__(k, data[k])
                        changed = True
                if changed:
                    article.updated = datetime.now()
                    article.save()
                    flash(u'Der Artikel wurde geändert.', True)
                else:
                    flash(u'Der Artikel wurde nicht verändert')
            return HttpResponseRedirect(href('admin', 'ikhaya', 'articles'))
    else:
        initial = {}
        if article:
            initial = {
                'subject': article.subject,
                'intro': article.intro,
                'text': article.text,
                'author': article.author,
                'category': article.category,
                'icon': article.icon,
                'pub_date': article.pub_date,
                'public': article.public,
                'slug': article.slug
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

    category_icons = dict((c.id, c.icon_id) for c in Category.objects.all())
    return {
        'form': form,
        'category_icons': category_icons,
        'article': article
    }


@require_manager
def ikhaya_article_delete(request, article):
    article = Article.objects.get(slug=article)
    if request.method == 'POST':
        if 'message-depublicate' in request.POST:
            article.public = False
            article.save()
            flash(u'Die Veröffentlichung des Artikels „%s“ wurde aufgehoben.'
                  % escape(article.subject))
        elif 'message-yes' in request.POST:
            article.delete()
            flash(u'Der Artikel „%s“ wurde erfolgreich gelöscht'
                  % escape(article.subject))
    else:
        flash(u'Möchtest du den Artikel „%s“ wirklich löschen?'
              % escape(article.subject), dialog=True,
              dialog_url=url_for(article, 'delete'),
              dialog_buttons=IKHAYA_ARTICLE_DELETE_BUTTONS)
    return HttpResponseRedirect(href('admin', 'ikhaya', 'articles'))


@require_manager
@templated('admin/ikhaya_categories.html')
def ikhaya_categories(request):
    sortable = Sortable(Category.objects.all(), request.GET, '-name')
    return {
        'table': sortable
    }


@require_manager
@templated('admin/ikhaya_category_edit.html')
def ikhaya_category_edit(request, category=None):
    """
    Display an interface to let the user create or edit an category.
    """
    def _add_field_choices():
        icons = [(i.id, i.identifier) for i in Icon.objects.all()]
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
                flash(u'Die Kategorie wurde erstellt', True)
            else:
                for k in data:
                    if category.__getattribute__(k) != data[k]:
                        category.__setattr__(k, data[k])
                category.save()
                flash(u'Die Kategorie wurde geändert.', True)
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


@require_manager
@templated('admin/ikhaya_icons.html')
def ikhaya_icons(request):
    sortable = Sortable(Icon.objects.all(), request.GET, 'identifier')
    return {
        'table': sortable
    }


@require_manager
@templated('admin/ikhaya_icon_edit.html')
def ikhaya_icon_edit(request, icon=None):
    """
    Display an interface to let the user create or edit an icon.
    """
    if icon:
        icon = Icon.objects.get(identifier=icon)

    if request.method == 'POST':
        form = EditIconForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            if not icon:
                icon = Icon()
            icon.identifier  = data['identifier']
            icon.save_img_file(data['img'].filename, data['img'].content)
            icon.save()
            flash(u'Das Icon wurde geändert.', True)
            return HttpResponseRedirect(href('admin', 'ikhaya', 'icons'))
    else:
        initial = {}
        if icon:
            initial = {
                'identifier': icon.identifier
            }
        form = EditIconForm(initial=initial)

    return {
        'form': form,
        'icon': icon
    }


@require_manager
@templated('admin/ikhaya_dates.html')
def ikhaya_dates(request):
    sortable = Sortable(Event.objects.all(), request.GET, 'title')
    return {
        'table': sortable
    }


@require_manager
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
            flash(u'Der Termin wurde geändert.', True)
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


@require_manager
@templated('admin/forums.html')
def forums(request):
    sortable = Sortable(Forum.objects.all(), request.GET, '-name')
    return {
        'table': sortable
    }

@require_manager
@templated('admin/forums_edit.html')
def forums_edit(request, id=None):
    """
    Display an interface to let the user create or edit an forum.
    If `id` is given, the forum with id `id` will be edited.
    """
    new_forum = id is None

    def _add_field_choices():
        categories = [(c.id, c.name) for c in Forum.objects.all()]
        form.fields['parent'].choices = [(-1,"Kategorie")] + categories

    if request.method == 'POST':
        form = EditForumForm(request.POST)
        _add_field_choices()
        if form.is_valid():
            data = form.cleaned_data
            if id is None:
                f = Forum()
            else:
                f = Forum.objects.get(id=id)
            f.name = data['name']
            f.position = data['position']
            if id is None:
                _check_forum_slug()
            else:
                if f.slug != data['slug']:
                    if Forum.objects.filter(slug=data['slug']):
                        form.errors['slug'] = (
                            (u'Bitte einen anderen Slug angeben,'
                             u'„%s“ ist schon vergeben.' % data['slug']),
                        )
                    else:
                        f.slug = data['slug']

            f.description = data['description']
            try:
                if int(data['parent']) != -1:
                    f.parent = Forum.objects.get(id=data['parent'])
            except Forum.DoesNotExist:
                form.errors['parent'] = (u'Forum %s existiert nicht' % data['parent'],)
            f.save()
            if not form.errors:
                flash(u'Das Forum „%s“ wurde erfolgreich %s' % (
                      f.name, new_forum and 'angelegt' or 'editiert'))
                return HttpResponseRedirect(href('admin', 'forum'))
            else:
                flash(u'Es sind Fehler aufgetreten, bitte behebe sie.', False)

    else:
        if id is None:
            form = EditForumForm()
        else:
            f = Forum.objects.get(id=id)
            form = EditForumForm({
                'name': f.name,
                'slug': f.slug,
                'description': f.description,
                'parent': f.parent_id,
                'position': f.position
            })
        _add_field_choices()
    return {
        'form': form,
        'new': new_forum,
        'forum_name': f.name
    }


@require_manager
@templated('admin/users.html')
def users(request):
    if request.method == 'POST':
        try:
            user = User.objects.get(username=request.POST.get('user'))
        except User.DoesNotExist:
            flash(u'Der Benutzer „%s“ existiert nicht.'
                  % escape(request.POST.get('user')))
        else:
            return HttpResponseRedirect(href('admin', 'users', 'edit', user.username))
    return {}


@require_manager
@templated('admin/edit_user.html')
def edit_user(request, username):
    #TODO: check for expensive SQL-Queries and other performance problems...
    #      ... this should be cleaned up -- it's damn unreadable for now...
    def _set_privileges():
        for v in value:
            setattr(privilege, 'can_' + v, True)
            for v in PRIVILEGES:
                if not v in value:
                    setattr(privilege, 'can_' + v, False)

    #: check if the user exists
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        flash(u'Der Benutzer „%s“ existiert nicht.'
              % escape(username))
        return HttpResponseRedirect(href('admin', 'users'))
    form = EditUserForm(model_to_dict(user))
    groups = Group.objects.select_related(depth=1)
    groups_joined, groups_not_joined = ([], [])

    if request.method == 'POST':
        form = EditUserForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            #: set the user attributes, avatar and forum privileges
            for key in ('username', 'is_active', 'date_joined', 'is_ikhaya_writer',
                        'website', 'interests', 'location', 'jabber', 'icq',
                        'msn', 'aim', 'yim', 'signature', 'coordinates_long',
                        'coordinates_lat', 'gpgkey'):
                setattr(user, key, data[key])
            if data['avatar']:
                user.save_avatar(data['avatar'])
            if data['new_password']:
                user.set_password(data['new_password'])

            #: forum privileges
            for key, value in request.POST.iteritems():
                if key.startswith('forum_privileges-'):
                    forum_slug = key.split('-', 1)[1]
                    try:
                        privilege = Privilege.objects.get(forum__slug=forum_slug)
                        privilege.user = user
                        privilege.forum = Forum.objects.get(slug=forum_slug)
                        _set_privileges()
                    except Privilege.DoesNotExist:
                        privilege = Privilege(
                            user=user,
                            forum=Forum.objects.get(slug=forum_slug)
                        )
                        _set_privileges()
                    privilege.save()

            # group editing
            groups_joined = [groups.get(name=gn) for gn in
                             request.POST.getlist('user_groups_joined')]
            groups_not_joined = [groups.get(name=gn) for gn in
                                request.POST.getlist('user_groups_not_joined')]
            user = User.objects.get(username=username)
            user.groups.remove(*groups_not_joined)
            user.groups.add(*groups_joined)
            user.save()

            flash(u'Das Benutzerprofil von "%s" wurde erfolgreich aktualisiert!' % user.username, True)
            if user.username != username:
                return HttpResponseRedirect(href('admin', 'users', user.username))
        else:
            flash(u'Es sind Fehler aufgetreten, bitte behebe sie!', False)

    forum_privileges = []
    forums = Forum.objects.all()
    for forum in forums:
        try:
            privilege = Privilege.objects.get(forum=forum, user=user)
            forum_privileges.append((forum.slug,
                forum.name,
                filter(lambda p: getattr(privilege, 'can_' + p, False),
                        [p[0] for p in PRIVILEGES_DETAILS])
                )
            )
        except Privilege.DoesNotExist:
            forum_privileges.append((forum.slug, forum.name, []))

    groups_joined = groups_joined or user.groups.all()
    groups_not_joined = groups_not_joined or [x for x in groups
                                              if not x in groups_joined]

    return {
        'user': user,
        'form': form,
        'user_forum_privileges': forum_privileges,
        'forum_privileges': PRIVILEGES_DETAILS,
        'user_groups': groups_joined,
        'joined_groups': [g.name for g in groups_joined],
        'not_joined_groups': [g.name for g in groups_not_joined]
    }


@require_manager
@templated('admin/groups.html')
def groups(request):
    if request.method == 'POST':
        try:
            group = Group.objects.get(name=request.POST.get('group'))
        except Group.DoesNotExist:
            flash(u'Die Gruppe „%s“ existiert nicht.', False)
        return HttpResponseRedirect(href('admin', 'groups'))
    flash(u'Not implemented yet...')
    return {
        'groups_exist': bool(Group.objects.count())
    }


@require_manager
@templated('admin/groups_edit.html')
def groups_edit(request, id=None):
    new = id is not None
    if request.method == 'POST':
        form = EditGroupForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
    else:
        form = EditGroupForm()
    return {
        'form': form
    }
