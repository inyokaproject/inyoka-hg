#-*- coding: utf-8 -*-
"""
    inyoka.admin.forms
    ~~~~~~~~~~~~~~~~~~

    Various forms for the admin control panel.

    :copyright: 2008 by Christopher Grebs, Benjamin Wiegand.
    :license: GNU GPL.
"""
from datetime import datetime
from django import newforms as forms
from inyoka.middlewares.registry import r
from inyoka.utils.forms import UserField, DATETIME_INPUT_FORMATS


class ConfigurationForm(forms.Form):
    global_message = forms.CharField(label=u'Globale Nachricht', widget=
                                     forms.Textarea(attrs={'rows': 3}),
                                     required=False)


class EditStaticPageForm(forms.Form):
    key = forms.CharField(label=u'Schlüssel', max_length=25, required=False)
    title = forms.CharField(label=u'Titel', max_length=200)
    content = forms.CharField(widget=forms.Textarea)


class EditBlogForm(forms.Form):
    name = forms.CharField(max_length=40, label=u'Name des Blogs')
    description = forms.CharField(label=u'Beschreibung',
                                  widget=forms.Textarea)
    blog_url = forms.URLField(label=u'URL des Blogs')
    feed_url = forms.URLField(label=u'URL des Feeds')
    icon = forms.ImageField(label=u'Icon', required=False)
    delete_icon = forms.BooleanField(label=u'Icon löschen', required=False)


class EditArticleForm(forms.Form):
    subject = forms.CharField(label=u'Überschrift', max_length=180,
                              widget=forms.TextInput(attrs={'size': 50}))
    intro = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}),
                            label=u'Einleitung')
    text = forms.CharField(widget=forms.Textarea(attrs={'rows': 15}),
                           label=u'Text')
    author = UserField(label=u'Autor', initial=r.request.user.username)
    category = forms.ChoiceField(label=u'Kategorie')
    icon = forms.ChoiceField(label=u'Icon', required=False)
    pub_date = forms.DateTimeField(label=u'Datum der Veröffentlichung',
                                   input_formats=DATETIME_INPUT_FORMATS,
                                   initial=datetime.now())
    public = forms.BooleanField(label=u'Veröffentlicht', required=False)
    slug = forms.CharField(label=u'Slug', max_length=100)


class EditCategoryForm(forms.Form):
    name = forms.CharField(label=u'Name', max_length=100)
    icon = forms.ChoiceField(label=u'Standardicon')


class EditIconForm(forms.Form):
    identifier = forms.CharField(label=u'Bezeichner', max_length=100)
    img = forms.FileField(label=u'Bild')
