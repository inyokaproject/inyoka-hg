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
from inyoka.utils.forms import UserField, DATETIME_INPUT_FORMATS, \
                               DATE_INPUT_FORMATS, TIME_INPUT_FORMATS
from inyoka.forum.acl import PRIVILEGES_DETAILS


class ConfigurationForm(forms.Form):
    global_message = forms.CharField(label=u'Globale Nachricht',
        widget=forms.Textarea(attrs={'rows': 3}), required=False,
        help_text = u'Diese Nachricht wird auf allen Seiten über dem Inhalt '
                    u'angezeigt. Um sie zu deaktivieren, lasse das Feld leer. '
                    u'Muss valides XHTML sein.')


class EditStaticPageForm(forms.Form):
    key = forms.CharField(label=u'Schlüssel', max_length=25, required=False,
                          help_text=u'Der Schlüssel bestimmt, unter welcher '
                                    u'Adresse die Seite abrufbar ist.')
    title = forms.CharField(label=u'Titel', max_length=200)
    content = forms.CharField(widget=forms.Textarea, label=u'Inhalt',
                              help_text=u'HTML ist erlaubt')


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
                                   input_formats=DATETIME_INPUT_FORMATS)
    public = forms.BooleanField(label=u'Veröffentlicht', required=False)
    slug = forms.CharField(label=u'Slug', max_length=100)


class EditCategoryForm(forms.Form):
    name = forms.CharField(label=u'Name', max_length=100)
    icon = forms.ChoiceField(label=u'Standardicon')


class EditIconForm(forms.Form):
    identifier = forms.CharField(label=u'Bezeichner', max_length=100)
    img = forms.FileField(label=u'Bild')


class CreateUserForm(forms.Form):
    username = forms.CharField(label=u'Benutzername', max_length=30)
    password = forms.CharField(label=u'Passwort')
    #XXX: use forms.EmailField after testing, see portal.user.User
    email = forms.CharField(label=u'E-Mail')
    authenticate = forms.BooleanField(label=u'Autentifizieren', required=False,
        help_text=(u'Der Benutzer bekommt eine Bestätigungsmail zugesandt'
                   u' und wird als inaktiv erstellt.'))


class EditUserForm(forms.Form):
    # personal informations
    username = forms.CharField(label=u'Benutzername', max_length=30)
    new_password = forms.CharField(label=u'Neues Passwort',
        required=False, help_text=(u'Ändert das Benutzerpasswort. '
                                   u'Bitte nur angeben, wenn benötigt'))
    #XXX: use `EmailField` after testing, see portal.user.User
    email = forms.CharField(label=u'E-Mail')
    is_active = forms.BooleanField(label=u'Aktiv', required=False)
    banned = forms.DateTimeField(label=u'Sperrung', required=False)
    date_joined = forms.DateTimeField(label=u'Angemeldet', required=False)

    #groups = forms.MultipleChoiceField(label=u'Gruppen', choices=[], required=False)
    post_count = forms.IntegerField(label=u'Beiträge', required=False)
    avatar = forms.ImageField(label=u'Avatar', required=False)

    # ikhaya permission
    is_ikhaya_writer = forms.BooleanField(label=u'Ikhaya Autor')

    # notification informations
    jabber = forms.CharField(label=u'Jabber', max_length=200, required=False)
    icq = forms.CharField(label=u'ICQ', max_length=16, required=False)
    msn = forms.CharField(label=u'MSN', max_length=200, required=False)
    aim = forms.CharField(label=u'AIM', max_length=200, required=False)
    yim = forms.CharField(label=u'YIM', max_length=200, required=False)

    # misc other things
    signature = forms.CharField(label=u'Signatur', required=False,
                                widget=forms.Textarea)
    coordinates_long = forms.DecimalField(label='Koordinaten (Breite)',
                       required=False, min_value=-90, max_value=90)
    coordinates_lat = forms.DecimalField(label=u'Koordinaten (Länge)',
                      required=False, min_value=-180, max_value=180)
    location = forms.CharField(label=u'Wohnort', max_length=200,
                               required=False)
    interests = forms.CharField(label=u'Interessen', max_length=200,
                                required=False)
    website = forms.URLField(label=u'Webseite', required=False)
    gpgkey = forms.RegexField('^(0x)?[0-9a-f]{8}$(?i)', required=False,
                              label=u'GPG-Schlüssel',  max_length=10)

    def clean_gpgkey(self):
        gpgkey = self.cleaned_data.get('gpgkey', '').upper()
        if gpgkey.startswith('0X'):
            gpgkey = gpgkey[2:]
        return gpgkey


class EditGroupForm(forms.Form):
    name = forms.CharField(label=u'Gruppenname', max_length=80)
    is_public = forms.BooleanField(label=u'Öffentliches Profil')
    forum_privileges = forms.MultipleChoiceField(label=u'Forum Privilegien',
                                                 required=False)


class EditForumForm(forms.Form):
    name = forms.CharField(label=u'Name', max_length=100)
    slug = forms.CharField(label=u'Slug', max_length=100, required=False)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), label=u'Beschreibung', required=False)
    parent = forms.ChoiceField(label=u'Elternforum', required=False)
    position = forms.IntegerField(label=u'Position', initial=0)


class EditEventForm(forms.Form):
    name = forms.CharField(label=u'Name', max_length=50)
    date = forms.DateField(label=u'Datum', input_formats=DATE_INPUT_FORMATS)
    time = forms.TimeField(label=u'Uhrzeit', input_formats=TIME_INPUT_FORMATS,
                           required=False)
    description = forms.CharField(label=u'Details', required=False,
                                  widget=forms.Textarea(attrs={'rows': 6}))
    location_town = forms.CharField(label=u'Ort', max_length=20, required=False)
    location = forms.CharField(label=u'Veranstaltungsort', max_length=50,
                               required=False)
    location_lat = forms.DecimalField(label=u'Koordinaten (Länge)',
                                      required=False,
                                      min_value=-180, max_value=180)
    location_long = forms.DecimalField(label=u'Koordinaten (Breite)',
                                      required=False,
                                      min_value=-90, max_value=90)

