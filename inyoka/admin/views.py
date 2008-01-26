#-*- coding: utf-8 -*-
"""
    inyoka.portal.admin
    ~~~~~~~~~~~~~~~~~~~

    This module holds the admin views.

    :copyright: 2008 by Christopher Grebs, Benjamin Wiegand.
    :license: GNU GPL.
"""
from datetime import datetime
from django.http import HttpResponse, HttpResponseRedirect
from django.newforms.models import model_to_dict
from inyoka.utils import slugify
from inyoka.utils.http import templated
from inyoka.utils.urls import url_for, href
from inyoka.utils.flashing import flash
from inyoka.utils.html import escape
from inyoka.utils.sortable import Sortable
from inyoka.utils.storage import storage
from inyoka.utils.pagination import Pagination
from inyoka.admin.forms import EditStaticPageForm, EditArticleForm, \
                               EditBlogForm, EditCategoryForm, EditIconForm, \
                               ConfigurationForm, EditUserForm
from inyoka.portal.models import StaticPage
from inyoka.portal.user import User
from inyoka.planet.models import Blog
from inyoka.ikhaya.models import Article, Suggestion, Category, Icon


@templated('admin/index.html')
def index(request):
    return {}


@templated('admin/configuration.html')
def config(request):
    if request.method == 'POST':
        form = ConfigurationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            for key in ('global_message',):
                storage[key] = data[key]
            flash(u'Die Einstellungen wurden gespeichert.', True)
    else:
        form = ConfigurationForm(initial=storage.get_many(['global_message']))
    return {
        'form': form
    }


@templated('admin/pages.html')
def pages(request):
    sortable = Sortable(StaticPage.objects.all(), request.GET, '-key')
    return {
        'table': sortable,
        'pages': sortable.get_objects(),
    }


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


def pages_delete(request, page_key):
    if not page_key:
        flash(u'Es wurde keine Seite zum löschen ausgewählt.')
    page = StaticPage.objects.get(key=page_key)
    if request.method == 'POST':
        if 'message-yes' in request.POST:
            page.delete()
            flash(u'Die Seite „%s“ wurde erfolgreich gelöscht'
                  % page.title)
    else:
        flash(u'Möchtest du die Seite „%s“ wirklich löschen?'
              % escape(page.title), dialog=True,
              dialog_url=href('admin', 'pages', 'delete', page_key))
    return HttpResponseRedirect(href('admin', 'pages'))


@templated('admin/planet.html')
def planet(request):
    return {
        'blogs': Blog.objects.all(),
    }


@templated('admin/planet_edit.html')
def planet_edit(request, blog=None):
    if blog:
        blog = Blog.objects.get(id=blog)

    if request.method == 'POST':
        form = EditBlogForm(request.POST, request.FILES)
        if form.is_valid():
            d = form.cleaned_data
            if not blog:
                blog = Blog(**d)
            else:
                for k in ('name', 'description', 'blog_url', 'feed_url'):
                    setattr(blog, k, d[k])
            if d['delete_icon']:
                blog.delete_icon()
            if d['icon']:
                blog.save_icon(d['icon'])
            blog.save()
            if not blog:
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


@templated('admin/ikhaya.html')
def ikhaya(request):
    pass


@templated('admin/ikhaya_articles.html')
def ikhaya_articles(request, page=1):
    sortable = Sortable(Article.objects.all(), request.GET, '-pub_date')
    pagination = Pagination(sortable.get_objects(), page,
                            href('admin', 'ikhaya', 'articles'), 25)
    return {
        'table': sortable,
        'articles': list(pagination.get_objects()),
        'pagination': pagination.generate()
    }


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


@templated('admin/ikhaya_categories.html')
def ikhaya_categories(request):
    sortable = Sortable(Category.objects.all(), request.GET, '-name')
    return {
        'table': sortable
    }


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


@templated('admin/ikhaya_icons.html')
def ikhaya_icons(request):
    sortable = Sortable(Icon.objects.all(), request.GET, 'identifier')
    return {
        'table': sortable
    }


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


@templated('admin/users.html')
def users(request):
    if 'q' in request.GET:
        try:
            user = User.objects.get(username=request.GET.get('q'))
        except User.DoesNotExist:
            flash(u'Der Benutzer %s existiert nicht.' % request.GET.get('q'))
        else:
            return HttpResponseRedirect(href('admin', 'users', user.username))
    return {}


def _on_search_user_query(request):
    #XXX: cache the results?
    qs = User.objects.filter(username__startswith=request.GET.get('q', ''))
    return HttpResponse('\n'.join(
        x.username for x in qs
    ))


@templated('admin/edit_user.html')
def edit_user(request, username):
    user = User.objects.filter(username=username).select_related()
    values = user.values()[0]
    form = EditUserForm(values)
    if request.method == 'POST':
        form = EditUserForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data
            user = user.get()
            for key in ('username', 'password', 'is_active', 'date_joined',
                        'website', 'interests', 'location', 'jabber', 'icq',
                        'msn', 'aim', 'yim', 'signature', 'coordinates',
                        'post_count'):
                setattr(user, key, data[key])
                if data['avatar']:
                    user.save_avatar(data['avatar'])
                user.save()
            flash(u'Das Benutzerprofil von "%s" wurde erfolgreich aktualisiert!' % user.username, True)
            if user.username != username:
                return HttpResponseRedirect(href('admin', 'users', user.username))
        else:
            flash(u'Es sind Fehler aufgetreten, bitte behebe sie!')
    return {
        'form': form
    }
