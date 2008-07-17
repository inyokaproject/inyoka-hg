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
from inyoka.utils.forms import UserField, DATETIME_INPUT_FORMATS, \
                               DATE_INPUT_FORMATS, TIME_INPUT_FORMATS, \
                               DateTimeWidget, EmailField
from inyoka.utils.html import cleanup_html
from inyoka.forum.acl import PRIVILEGES_DETAILS
from inyoka.portal.models import StaticFile


class ConfigurationForm(forms.Form):
    global_message = forms.CharField(label=u'Globale Nachricht',
        widget=forms.Textarea(attrs={'rows': 3}), required=False,
        help_text = u'Diese Nachricht wird auf allen Seiten über dem Inhalt '
                    u'angezeigt. Um sie zu deaktivieren, lasse das Feld leer. '
                    u'Muss valides XHTML sein.')
    blocked_hosts = forms.CharField(label=u'Verbotene Hosts für E-Mail-Adressen',
        widget=forms.Textarea(attrs={'rows': 3}), required=False,
        help_text = u'Benutzer können keine E-Mail-Adressen von diesen Hosts '
                    u'zum Registrieren verwenden.')
    team_icon = forms.ImageField(label=u'Teamicon', required=False)
    max_avatar_width = forms.IntegerField(min_value=1)
    max_avatar_height = forms.IntegerField(min_value=1)
    max_signature_length = forms.IntegerField(min_value=1,
        label=u'Maximale Signaturlänge')
    max_signature_lines = forms.IntegerField(min_value=1,
        label=u'Maximale Zeilenanzahl in Signatur')
    get_ubuntu_link = forms.URLField(required=False,
        label=u'Der Downloadlink für die Startseite')
    get_ubuntu_description = forms.CharField(label=u'Beschreibung des Links')
    wiki_newpage_template = forms.CharField(required=False,
        widget=forms.Textarea(attrs={'rows': 5}),
        label=u'Standardtext beim Anlegen neuer Wiki-Seiten')
    wiki_newpage_root = forms.CharField(required=False,
        label=u'Unter welcher Wikiseite sollen neue Seiten erstellt werden?')

    def clean_global_message(self):
        return cleanup_html(self.cleaned_data.get('global_message', ''))


class EditStaticPageForm(forms.Form):
    key = forms.CharField(label=u'Schlüssel', max_length=25, required=False,
                          help_text=u'Der Schlüssel bestimmt, unter welcher '
                                    u'Adresse die Seite abrufbar ist.')
    title = forms.CharField(label=u'Titel', max_length=200)
    content = forms.CharField(widget=forms.Textarea, label=u'Inhalt',
                              help_text=u'Muss gültiges XHTML sein.')


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
    author = UserField(label=u'Autor', initial='',
        help_text=u'Wenn du dieses Feld leer lässt, wirst du automatisch '
                  u'als Autor eingetragen.')
    category_id = forms.ChoiceField(label=u'Kategorie')
    icon_id = forms.ChoiceField(label=u'Icon', required=False,
            help_text=u'Wenn du dieses Feld leer lässt, wird automatisch '
                      u'Icon der Kategorie ausgewählt')
    pub_date = forms.DateTimeField(label=u'Datum der Veröffentlichung',
        input_formats=DATETIME_INPUT_FORMATS, help_text=u'Wenn das Datum in '
        u'der Zukunft liegt, wird der Artikel bis zu diesem Zeitpunkt nicht '
        u'angezeigt.', widget=DateTimeWidget)
    public = forms.BooleanField(label=u'Veröffentlicht', required=False)
    slug = forms.CharField(label=u'Slug', max_length=100, required=False,
        help_text=u'Dies ist die URL, unter der der Artikel liegt. Lasse das '
                  u'Feld frei, um ihn automatisch generieren zu lassen '
                  u'(empfohlen).')
    comments_enabled = forms.BooleanField(label=u'Kommentare erlaubt',
                                          required=False)


class EditCategoryForm(forms.Form):
    name = forms.CharField(label=u'Name', max_length=100)
    icon = forms.ChoiceField(label=u'Standardicon')


class EditFileForm(forms.Form):
    file = forms.FileField(label=u'Datei', required=False)
    is_ikhaya_icon = forms.BooleanField(label=u'Ist Ikhaya-Icon',
            required=False,
            help_text=u'Wähle dieses Feld aus, wenn die Datei im Auswahlfeld '
                      u'für Artikel- und Kategorie-Icons erscheinen soll.')

    def __init__(self, file=None, *args, **kwargs):
        self._file = file
        forms.Form.__init__(self, *args, **kwargs)

    def clean_file(self):
        data = self.cleaned_data.get('file')
        if data is None and not self._file:
            raise forms.ValidationError(u'Bitte eine Datei auswählen')
        if data:
            filename = data.filename
            changed = filename != (self._file and self._file.identifier or None)
            if changed and list(StaticFile.objects.filter(identifier=filename)):
                raise forms.ValidationError(u'Eine Datei mit diesem Namen '
                                            u'existiert bereits.')
        return data


class CreateUserForm(forms.Form):
    username = forms.CharField(label=u'Benutzername', max_length=30)
    password = forms.CharField(label=u'Passwort')
    email = EmailField(label=u'E-Mail')
    authenticate = forms.BooleanField(label=u'Autentifizieren', initial=True,
        required=False, help_text=(u'Der Benutzer bekommt eine '
            u'Bestätigungsmail zugesandt und wird als inaktiv erstellt.'))


class EditUserForm(forms.Form):
    # personal informations
    username = forms.CharField(label=u'Benutzername', max_length=30)
    new_password = forms.CharField(label=u'Neues Passwort',
        required=False, widget=forms.PasswordInput(render_value=False),
        help_text=(u'Ändert das Benutzerpasswort. Bitte nur angeben, '
                   u'wenn benötigt'))
    confirm_password = forms.CharField(label=u'Neues Passwort (Wiederholung)',
        required=False, widget=forms.PasswordInput(render_value=False))
    email = forms.CharField(label=u'E-Mail', required=False)
    is_active = forms.BooleanField(label=u'Aktiv', required=False)
    banned = forms.DateTimeField(label=u'Sperrung', required=False)
    date_joined = forms.DateTimeField(label=u'Angemeldet', required=False)

    post_count = forms.IntegerField(label=u'Beiträge', required=False)
    avatar = forms.ImageField(label=u'Avatar', required=False)
    member_title = forms.CharField(label=u'Benutzer-Titel', required=False)
    permissions = forms.MultipleChoiceField(label=u'Privilegien',
                                            required=False)

    # notification informations
    jabber = forms.CharField(label=u'Jabber', max_length=200, required=False)
    icq = forms.CharField(label=u'ICQ', max_length=16, required=False)
    msn = forms.CharField(label=u'MSN', max_length=200, required=False)
    aim = forms.CharField(label=u'AIM', max_length=200, required=False)
    yim = forms.CharField(label=u'YIM', max_length=200, required=False)
    skype = forms.CharField(label=u'Skype', required=False)
    wengophone = forms.CharField(label=u'WengoPhone', required=False)
    sip = forms.CharField(label=u'SIP', required=False)

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
    launchpad = forms.CharField(label=u'Launchpad-Nickname', required=False)
    gpgkey = forms.RegexField('^(0x)?[0-9a-f]{8}$(?i)', required=False,
                              label=u'GPG-Schlüssel',  max_length=10)

    delete_avatar = forms.BooleanField(label=u'Avatar löschen', required=False)

    def clean_gpgkey(self):
        gpgkey = self.cleaned_data.get('gpgkey', '').upper()
        if gpgkey.startswith('0X'):
            gpgkey = gpgkey[2:]
        return gpgkey

    def clean_confirm_password(self):
        """
        Validates that the two password inputs match.
        """
        data = self.cleaned_data
        if 'new_password' in data and 'confirm_password' in data:
            if data['new_password'] == data['confirm_password']:
                return data['confirm_password']
            raise forms.ValidationError(
                u'Das Passwort muss mit der Paswortbestätigung übereinstimmen!'
            )
        else:
            raise forms.ValidationError(
                u'Du musst ein Passwort und eine Passwortbestätigung angeben!'
            )


class EditGroupForm(forms.Form):
    name = forms.CharField(label=u'Gruppenname', max_length=80)
    permissions = forms.MultipleChoiceField(label=u'Privilegien',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'permission'}),
        required=False)
    forum_privileges = forms.MultipleChoiceField(label=u'Forum Privilegien',
                                                 required=False)


class EditForumForm(forms.Form):
    name = forms.CharField(label=u'Name', max_length=100)
    slug = forms.CharField(label=u'Slug', max_length=100, required=False)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}),
                                  label=u'Beschreibung', required=False)
    parent = forms.ChoiceField(label=u'Elternforum', required=False)
    position = forms.IntegerField(label=u'Position', initial=0)

    welcome_msg_subject = forms.CharField(label=u'Titel', max_length=120,
        required=False)
    welcome_msg_text = forms.CharField(label=u'Text', required=False)

    def clean_welcome_msg_subject(self):
        data = self.cleaned_data
        if data.get('welcome_msg_text') and not data.get('welcome_msg_subject'):
            raise forms.ValidationError(u'Du musst einen Titel angeben für die'
                u' Willkommensnachricht')
        return data['welcome_msg_subject']

    def clean_welcome_msg_text(self):
        data = self.cleaned_data
        if data.get('welcome_msg_subject') and not data.get('welcome_msg_text'):
            raise forms.ValidationError(u'Du musst einen Text für die '
                u'Willkommensnachricht eingeben.')
        return data['welcome_msg_text']


class EditStyleForm(forms.Form):
    styles = forms.CharField(label=u'Styles', widget=forms.Textarea(
                             attrs={'rows': 20}), required=False)


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
