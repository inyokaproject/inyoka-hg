# -*- coding: utf-8 -*-
"""
    inyoka.portal.forms
    ~~~~~~~~~~~~~~~~~~~

    Various forms for the portal.

    :copyright: 2007 by Benjamin Wiegand, Christopher Grebs, Marian Sigler.
    :license: GNU GPL, see LICENSE for more details.
"""
import md5
from django import newforms as forms
from django.conf import settings
from inyoka.portal.user import User
from inyoka.utils import is_valid_username
from inyoka.utils.urls import href
from inyoka.utils.forms import CaptchaWidget, CaptchaField, HiddenCaptchaField
from inyoka.wiki.parser import validate_signature, SignatureError


#: Some constants used for ChoiceFields
NOTIFY_BY_CHOICES = (
    ('mail', 'E-Mail'),
    ('jabber', 'Jabber'),
)

NOTIFICATION_CHOICES = (
    ('topic_move', 'Verschieben eines eigenen Themas'),
    ('pm_new', 'Neuer privaten Nachricht')
)

SEARCH_AREA_CHOICES = (
    ('all', 'Überall'),
    ('wiki', 'Wiki'),
    ('forum', 'Forum'),
    ('ikhaya', 'Ikhaya'),
    ('planet', 'Planet')
)

SEARCH_SORT_CHOICES = (
    ('relevance', 'Relevanz'),
    ('date', 'Datum')
)


class LoginForm(forms.Form):
    """Simple form for the login dialog"""
    username = forms.CharField(label='Benutzername')
    password = forms.CharField(label='Passwort', widget=
        forms.PasswordInput(render_value=False))
    permanent = forms.BooleanField(label='Eingeloggt bleiben',
                                   widget=forms.CheckboxInput)


class RegisterForm(forms.Form):
    """
    Form for registering a new user account.

    Validates that the requested username is not already in use, and
    requires the password to be entered twice to catch typos.
    The user also needs to confirm our terms of usage and there are some
    techniques for bot catching included e.g a CAPTCHA and a hidden captcha
    for bots that just fill out everything.
    """
    username = forms.CharField(label='Benutzername')
    #email = forms.EmailField(label='E-Mail')
    # allow @localhost urls for easier testing
    email = forms.CharField(label='E-Mail', help_text=u'Wir benötigen deine '
        u'E-Mail-Adresse, um dir ein neues Passwort zu schicken, falls du '
        u'deines vergessen haben solltest. ubuntuusers.de <a href="%s">'
        u'garantiert</a>, dass sie nicht weitergegeben wird.' % href('portal',
                                                               'datenschutz'))
    password = forms.CharField(label='Passwort', widget=
        forms.PasswordInput(render_value=False))
    confirm_password = forms.CharField(label=u'Passwortbestätigung',
        widget=forms.PasswordInput(render_value=False))
    captcha = CaptchaField(label='CAPTCHA')
    hidden_captcha = HiddenCaptchaField(required=False)
    terms_of_usage = forms.BooleanField(widget=forms.CheckboxInput)

    def clean_username(self):
        """
        Validates that the username is alphanumeric and is not already
        in use.
        """
        if 'username' in self.cleaned_data:
            if not is_valid_username(self.cleaned_data['username']):
                #XXX: add a note which characters are allowed
                raise forms.ValidationError(
                    u'Dein Benutzername enthält nicht benutzbare Zeichen'
                )
            try:
                user = User.objects.get(
                    username__exact=self.cleaned_data['username']
                )
            except User.DoesNotExist:
                return self.cleaned_data['username']

            raise forms.ValidationError(
                u'Der Benutzername ist leider schon vergeben. '
                u'Bitte wähle einen anderen.'
            )
        else:
            raise forms.ValidationError(
                u'Du musst einen Benutzernamen angeben!'
            )

    def clean_confirm_password(self):
        """
        Validates that the two password inputs match.
        """
        if 'password' in self.cleaned_data and 'confirm_password' in self.cleaned_data:
            if self.cleaned_data['password'] == self.cleaned_data['confirm_password']:
                return self.cleaned_data['confirm_password']
            raise forms.ValidationError(
                u'Das Passwort muss mit der Passwortbestätigung übereinstimmen!'
            )
        else:
            raise forms.ValidationError(
                u'Du musst ein Passwort und eine Passwortbestätigung angeben!'
            )

    def clean_terms_of_usage(self):
        """Validates that the user agrees our terms of usage"""
        if self.cleaned_data.get('terms_of_usage', False):
            return True
        raise forms.ValidationError(
            u'Du musst unsere Hinweise zur Nutzung von ubuntuusers.de '
            u'gelesen haben und bestätigen!'
        )

    def clean_email(self):
        """
        Validates if the required field `email` contains
        a non existing mail address.
        """
        if 'email' in self.cleaned_data:
            try:
                user = User.objects.get(email__exact=self.cleaned_data['email'])
            except User.DoesNotExist:
                return self.cleaned_data['email']

            raise forms.ValidationError(
                u'Die angegebene E-Mail-Adresse wird bereits benutzt!'
                #TODO: add some link to the lost password function
            )
        else:
            raise forms.ValidationError(
                u'Du musst eine E-Mail-Adresse angeben!'
            )


class LostPasswordForm(forms.Form):
    """
    Form for the lost password form.

    It's similar to the register form and uses
    a hidden and a visible image CAPTCHA too.
    """
    username = forms.CharField(label=u'Benutzername', required=False)
    #email = forms.EmailField(label=u'E-Mail', required=False)
    email = forms.CharField(label=u'E-Mail', required=False)
    captcha = CaptchaField(label='CAPTCHA')
    hidden_captcha = HiddenCaptchaField(required=False)

    def clean(self):
        data = super(self.__class__, self).clean()
        if 'username' in data and 'email' in data \
            and data['username'] and data['email']:
            try:
                self.user = User.objects.get(username=data['username'], email=data['email'])
            except User.DoesNotExist:
                raise forms.ValidationError(
                    u'Der angegebene Benutzername und die angegebene '
                    u'E-Mail-Adresse stimmen nicht überein!'
                )
        elif 'username' in data and data['username']:
            try:
                self.user = User.objects.get(username=data['username'])
            except User.DoesNotExist:
                raise forms.ValidationError(
                    u'Einen Benutzer „%s“ gibt es nicht!' % data['username']
                )
        elif 'email' in data and data['email']:
            try:
                self.user = User.objects.get(email=data['email'])
            except User.DoesNotExist:
                raise forms.ValidationError(
                    u'Einen Benutzer mit der E-Mail-Adresse „%s“ '
                    u'gibt es nicht!' % data['email']
                )
        else:
            raise forms.ValidationError(
                u'Bitte entweder einen Benutzernamen oder eine E-Mail-Adresse '
                u'angeben!'
            )


class SetNewPasswordForm(forms.Form):
    username = forms.CharField(widget=forms.HiddenInput)
    new_password_key = forms.CharField(widget=forms.HiddenInput)
    password = forms.CharField(label='Neues Passwort',
                               widget=forms.PasswordInput)
    password_confirm = forms.CharField(label='Neues Passwort (Bestätigung)',
                                       widget=forms.PasswordInput)

    def clean(self):
        data = super(self.__class__, self).clean()
        if data['password'] != data['password_confirm']:
            raise forms.ValidationError(u'Die Passwörter stimmen nicht '
                                        u'überein!')
        try:
            data['user'] = User.objects.get(username=self['username'].data,
                               new_password_key=self['new_password_key'].data)
        except User.DoesNotExist:
            raise forms.ValidationError(u'Der Benutzer konnte nicht gefunden '
                                        u'werden oder der Bestätigungskey '
                                        u'ist nicht mehr gültig.')
        return data


class ChangePasswordForm(forms.Form):
    """Simple form for changing the password."""
    old_password = forms.CharField(label='Altes Passwort',
                                   widget=forms.PasswordInput,
                                   required=False)
    new_password = forms.CharField(label='Neues Passwort')
                                   #widget=forms.PasswordInput)


class UserCPSettingsForm(forms.Form):
    """
    Form used for the user control panel -- settings
    dialog.
    """
    notify = forms.MultipleChoiceField(required=False,
                                       choices=NOTIFY_BY_CHOICES)
    notifications = forms.MultipleChoiceField(required=False,
                                              choices=NOTIFICATION_CHOICES)
    hide_avatars = forms.BooleanField()
    hide_signatures = forms.BooleanField()


class UserCPProfileForm(forms.Form):
    avatar = forms.ImageField(label='Avatar', required=False)
    delete_avatar = forms.BooleanField(label=u'Avatar löschen')
    email = forms.EmailField(label='E-Mail', required=False)
    jabber = forms.CharField(label='Jabber', required=False)
    icq = forms.CharField(label='ICQ', required=False)
    msn = forms.CharField(label='MSN Messenger', required=False)
    aim = forms.CharField(label='AIM', required=False)
    yim = forms.CharField(label='Yahoo Instant Messenger', required=False)
    signature = forms.CharField(widget=forms.Textarea, label='Signatur',
                               required=False)
    coordinates_long = forms.DecimalField(label='Koordinaten (Breite)',
                       required=False, min_value=-90, max_value=90)
    coordinates_lat = forms.DecimalField(label=u'Koordinaten (Länge)',
                      required=False, min_value=-180, max_value=180)
    location = forms.CharField(label='Wohnort', required=False)
    occupation = forms.CharField(label='Beruf', required=False)
    interests = forms.CharField(label='Interessen', required=False)
    website = forms.URLField(label='Webseite', required=False)
    gpgkey = forms.RegexField('^(0x)?[0-9a-f]{8}$(?i)', label=u'GPG-Schlüssel',
                 max_length=10, required=False, help_text=u'Hier kannst du '
                 u'deinen GPG-Public-Key eintragen. Näheres zu diesem Thema '
                 u'erfährst du <a href="http://wiki.ubuntuusers.de/GnuPG/Web'
                 u'_of_Trust">hier</a>.')

    def clean_gpgkey(self):
        gpgkey = self.cleaned_data.get('gpgkey', '').upper()
        if gpgkey.startswith('0X'):
            gpgkey = gpgkey[2:]
        return gpgkey

    def clean_signature(self):
        signature = self.cleaned_data.get('signature', '')
        try:
            validate_signature(signature)
        except SignatureError, e:
            raise forms.ValidationError(e.message)
        return signature


class SearchForm(forms.Form):
    """The search formular"""
    query = forms.CharField(label='Suchbegriffe:', widget=forms.TextInput(attrs={'size':'100'}))
    area = forms.ChoiceField(label='Bereich:', choices=SEARCH_AREA_CHOICES,
                             required=False)
    page = forms.IntegerField(required=False, widget=forms.HiddenInput)
    per_page = forms.IntegerField(required=False, widget=forms.HiddenInput)
    date_begin = forms.DateTimeField(required=False)
    date_end = forms.DateTimeField(required=False)
    sort = forms.ChoiceField(label='Sortieren:', choices=SEARCH_SORT_CHOICES,
        required=False)


class PrivateMessageForm(forms.Form):
    """Form for writing a new private message"""
    recipient = forms.CharField(label=u'Empfänger',
        help_text="Mehrere Namen mit Semikolon getrennt eingeben.")
    subject = forms.CharField(label=u'Betreff')
    text = forms.CharField(label=u'Text', widget=forms.Textarea)


class DeactivateUserForm(forms.Form):
    """Form for the user control pannel -- deactivate_user view."""
    password_confirmation = forms.CharField(widget=forms.PasswordInput)


class SubscriptionForm(forms.Form):
    #: this is a list of integers of the subscriptions that should get deleted
    delete = forms.MultipleChoiceField()
