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
    author = UserField(label=u'Autor', initial=(r.request and r.request.user.username or ''))
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


class EditUserForm(forms.Form):
    # personal informations
    username = forms.CharField(label=u'Benutzername', max_length=30)
    new_password = forms.CharField(label=u'Neues Passwort', max_length=128,
        required=False, help_text=(u'Ändert das Benutzerpasswort. '
                                   u'Bitte nur angeben, wenn benötigt.'))
    is_active = forms.BooleanField(label=u'Aktiv', required=False)
    date_joined = forms.DateTimeField(label=u'Angemeldet', required=False)

    #groups = forms.MultipleChoiceField(label=u'Gruppen', choices=[], required=False)
    post_count = forms.IntegerField(label=u'Beiträge', required=False)
    avatar = forms.ImageField(label=u'Avatar', required=False)

    # notification informations
    jabber = forms.CharField(label=u'Jabber', max_length=200, required=False)
    icq = forms.CharField(label=u'ICQ', max_length=16, required=False)
    msn = forms.CharField(label=u'MSN', max_length=200, required=False)
    aim = forms.CharField(label=u'AIM', max_length=200, required=False)
    yim = forms.CharField(label=u'YIM', max_length=200, required=False)

    # misc other things
    signature = forms.CharField(label=u'Signatur', required=False,
                                widget=forms.Textarea)
    coordinates = forms.CharField(label=u'Koordinaten', required=False)
    location = forms.CharField(label=u'Wohnort', max_length=200, required=False)
    interests = forms.CharField(label=u'Interessen', max_length=200, required=False)
    website = forms.URLField(label=u'Webseite', required=False)
    gpgkey = forms.RegexField('^(0x)?[0-9a-f]{8}$(?i)', label=u'GPG-Schlüssel', 
                              max_length=10, required=False)

    def clean_gpgkey(self):
        gpgkey = self.cleaned_data.get('gpgkey', '').upper()
        if gpgkey.startswith('0X'):
           gpgkey = gpgkey[2:]
        return gpgkey


    forum_privileges = forms.MultipleChoiceField(required=False)


class EditDateForm(forms.Form):
    date = forms.DateTimeField(input_formats=DATETIME_INPUT_FORMATS,
                               initial=datetime.now())
    title = forms.CharField()
    description = forms.CharField(widget=forms.Textarea)


class EditForumForm(forms.Form):
    name = forms.CharField(label=u'Name', max_length=100)
    slug = forms.CharField(label=u'Slug', max_length=100, required=False)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label=u'Beschreibung', required=False)
    parent = forms.ChoiceField(label=u'Elternforum', required=False)
    position = forms.IntegerField(label=u'Position', initial=0)
