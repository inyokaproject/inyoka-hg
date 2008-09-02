#-*- coding: utf-8 -*-
"""
    inyoka.admin.forms
    ~~~~~~~~~~~~~~~~~~

    Various forms for the admin control panel.

    :copyright: 2008 by Christopher Grebs, Benjamin Wiegand.
    :license: GNU GPL.
"""
import datetime
from django import forms
from inyoka.utils.forms import UserField, DATETIME_INPUT_FORMATS, \
                               DATE_INPUT_FORMATS, TIME_INPUT_FORMATS, \
                               DateTimeWidget, EmailField
from inyoka.utils.html import cleanup_html
from inyoka.utils.user import normalize_username
from inyoka.portal.models import StaticFile
from inyoka.portal.user import Group, User


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
    team_icon = forms.ImageField(label=u'Globales Teamicon', required=False,
        help_text=u'Beachte bitte untenstehende Angaben zu der Maximalgröße')
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
    team_icon_width = forms.IntegerField(min_value=1, required=False)
    team_icon_height = forms.IntegerField(min_value=1, required=False)
    license_note = forms.CharField(required=False, label=u'Lizenzhinweis',
                                   widget=forms.Textarea(attrs={'rows': 2}))

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
            filename = data.name
            changed = filename != (self._file and self._file.identifier or None)
            if changed:
                exists = bool(StaticFile.objects.filter(identifier__iexact=filename))
                if exists:
                    raise forms.ValidationError(u'Eine Datei mit diesem Namen '
                                                u'existiert bereits.')
        return data


class CreateUserForm(forms.Form):
    username = forms.CharField(label=u'Benutzername', max_length=30)
    password = forms.CharField(label=u'Passwort',
        widget=forms.PasswordInput(render_value=False))
    confirm_password = forms.CharField(label=u'Passwort (Wiederholung)',
        widget=forms.PasswordInput(render_value=False))
    email = EmailField(label=u'E-Mail')
    authenticate = forms.BooleanField(label=u'Autentifizieren', initial=True,
        required=False, help_text=(u'Der Benutzer bekommt eine '
            u'Bestätigungsmail zugesandt und wird als inaktiv erstellt.'))

    def clean_username(self):
        """
        Validates that the username is alphanumeric and is not already
        in use.
        """
        data = self.cleaned_data
        if 'username' in data:
            try:
                username = normalize_username(data['username'])
            except ValueError:
                raise forms.ValidationError(u'Der Benutzername enthält '
                                            u'nicht benutzbare Zeichen')
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return username

            raise forms.ValidationError(
                u'Der Benutzername ist leider schon vergeben. '
                u'Bitte wähle einen anderen.'
            )
        else:
            raise forms.ValidationError(u'Du musst einen Benutzernamen angeben!')

    def clean_confirm_password(self):
        """
        Validates that the two password inputs match.
        """
        data = self.cleaned_data
        if 'password' in data and 'confirm_password' in data:
            if data['password'] == data['confirm_password']:
                return data['confirm_password']
            raise forms.ValidationError(
                u'Das Passwort muss mit der Paswortbestätigung übereinstimmen!'
            )
        else:
            raise forms.ValidationError(
                u'Du musst ein Passwort und eine Passwortbestätigung angeben!'
            )

    def clean_email(self):
        """
        Validates if the required field `email` contains
        a non existing mail address.
        """
        if 'email' in self.cleaned_data:
            try:
                user = User.objects.get(email=self.cleaned_data['email'])
            except User.DoesNotExist:
                return self.cleaned_data['email']

            raise forms.ValidationError(
                u'Die angegebene E-Mail-Adresse wird bereits benutzt!'
            )
        else:
            raise forms.ValidationError(
                u'Du musst eine E-Mail-Adresse angeben!'
            )


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
    status = forms.ChoiceField(label=u'Status', required=False,
                                   choices=enumerate([
                                       u'noch nicht aktiviert',
                                       u'aktiv',
                                       u'gebannt',
                                       u'hat sich selbst gelöscht']))
    banned_until = forms.DateTimeField(label=u'Automatisch entsperren', required=False,
                       help_text='leer lassen, um dauerhaft zu bannen (wirkt nur wenn Status=gebannt)')
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

    primary_group = forms.CharField(label=u'Primäre Gruppe', required=False,
        widget=forms.TextInput({'readonly': 'readonly'}),
        help_text=u'Wird unter anderem für das anzeigen des Team-Icons verwendet')

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
                u'Das Passwort muss mit der Passwortbestätigung übereinstimmen!'
            )
        else:
            raise forms.ValidationError(
                u'Du musst ein Passwort und eine Passwortbestätigung angeben!'
            )

    def clean_banned_until(self):
        """
        Keep the user from setting banned_until if status is not banned.
        This is to avoid confusion because this was previously possible.
        """
        data = self.cleaned_data
        if data['banned_until'] is None:
            return
        if data['status'] not in (2, '2'):
            raise forms.ValidationError(
                u'Der Benutzer ist gar nicht gebannt'
            )
        if data['banned_until'] < datetime.datetime.now():
            #XXX: timezone does not work. but those few hours … :)
            raise forms.ValidationError(
                u'Der Zeitpunkt liegt in der Vergangenheit'
            )
        return data['banned_until']



class EditGroupForm(forms.Form):
    name = forms.CharField(label=u'Gruppenname', max_length=80)
    permissions = forms.MultipleChoiceField(label=u'Privilegien',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'permission'}),
        required=False)
    forum_privileges = forms.MultipleChoiceField(label=u'Forumsprivilegien',
                                                 required=False)
    icon = forms.ImageField(label=u'Team-Icon', required=False)
    delete_icon = forms.BooleanField(label=u'Team-Icon löschen', required=False)
    import_icon_from_global = forms.BooleanField(label=u'Globales Team-Icon benutzen',
        required=False)


class CreateGroupForm(EditGroupForm):

    def clean_name(self):
        """Validates that the name is alphanimeric and is not already in use."""

        data = self.cleaned_data
        if 'name' in data:
            try:
                name = normalize_username(data['name'])
            except ValueError:
                raise forms.ValidationError(u'Der Gruppenname enthält '
                                            u'nicht benutzbare Zeichen')
            try:
                group = Group.objects.get(name=name)
            except Group.DoesNotExist:
                return name

            raise forms.ValidationError(
                u'Der Gruppename ist leider schon vergeben. '
                u'Bitte wähle einen anderen.'
            )
        else:
            raise forms.ValidationError(u'Du musst einen Gruppennamen angeben!')


class EditForumForm(forms.Form):
    name = forms.CharField(label=u'Name', max_length=100)
    slug = forms.CharField(label=u'Slug', max_length=100, required=False)
    description = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}),
                                  label=u'Beschreibung', required=False)
    parent = forms.ChoiceField(label=u'Elternforum', required=False)
    position = forms.IntegerField(label=u'Position', initial=0)

    welcome_msg_subject = forms.CharField(label=u'Titel', max_length=120,
        required=False)
    welcome_msg_text = forms.CharField(label=u'Text', required=False,
                                       widget=forms.Textarea(attrs={'rows': 3}))
    newtopic_default_text = forms.CharField(label=u'Standardtext für neue Themen',
                                            widget=forms.Textarea(attrs={'rows': 3}),
                                            required=False)

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
