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
from inyoka.conf import settings
from inyoka.portal.user import User
from inyoka.utils.user import normalize_username
from inyoka.utils.dates import TIMEZONES
from inyoka.utils.urls import href, is_safe_domain
from inyoka.utils.forms import CaptchaWidget, CaptchaField, DateTimeWidget, \
                               HiddenCaptchaField, EmailField, JabberField
from inyoka.wiki.parser import validate_signature, SignatureError
from inyoka.utils.local import current_request
from inyoka.utils.html import escape


#: Some constants used for ChoiceFields
NOTIFY_BY_CHOICES = (
    ('mail', 'E-Mail'),
    ('jabber', 'Jabber'),
)

NOTIFICATION_CHOICES = (
    ('topic_move', 'Verschieben eines eigenen Themas'),
    ('pm_new', 'Neuer privater Nachricht')
)

SEARCH_AREA_CHOICES = (
    ('all', 'Überall'),
    ('wiki', 'Wiki'),
    ('forum', 'Forum'),
    ('ikhaya', 'Ikhaya'),
    ('planet', 'Planet'),
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
                                   required=False)


class RegisterForm(forms.Form):
    """
    Form for registering a new user account.

    Validates that the requested username is not already in use, and
    requires the password to be entered twice to catch typos.
    The user also needs to confirm our terms of usage and there are some
    techniques for bot catching included e.g a CAPTCHA and a hidden captcha
    for bots that just fill out everything.
    """
    username = forms.CharField(label='Benutzername', max_length=30)
    email = EmailField(label='E-Mail', help_text=u'Wir benötigen deine '
        u'E-Mail-Adresse, um dir ein neues Passwort zu schicken, falls du '
        u'es vergessen haben solltest. ubuntuusers.de <a href="%s">'
        u'garantiert</a>, dass sie nicht weitergegeben wird.'
        % href('portal', 'datenschutz'))
    password = forms.CharField(label='Passwort',
        widget=forms.PasswordInput(render_value=False))
    confirm_password = forms.CharField(label=u'Passwortbestätigung',
        widget=forms.PasswordInput(render_value=False))
    captcha = CaptchaField(label='CAPTCHA')
    hidden_captcha = HiddenCaptchaField(required=False)
    terms_of_usage = forms.BooleanField()

    def clean_username(self):
        """
        Validates that the username is alphanumeric and is not already
        in use.
        """
        if 'username' in self.cleaned_data:
            try:
                username = normalize_username(self.cleaned_data['username'])
            except ValueError:
                raise forms.ValidationError(
                    u'Dein Benutzername enthält nicht benutzbare Zeichen'
                )
            try:
                user = User.objects.get(username__exact=username)
            except User.DoesNotExist:
                return username

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
                u' Fals du dein Passwort vergessen hast, kannst du es '
                u'<a href="%s">wiederherstellen lassen</a>' % escape(
                    href('portal', 'lost_password'))
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
    email = EmailField(label=u'E-Mail', required=False)
    captcha = CaptchaField(label='CAPTCHA')
    hidden_captcha = HiddenCaptchaField(required=False)

    def clean(self):
        data = super(LostPasswordForm, self).clean()
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
        data = super(SetNewPasswordForm, self).clean()
        if 'password' not in data or 'password_confirm' not in data or \
           data['password'] != data['password_confirm']:
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
                                   widget=forms.PasswordInput)
    new_password = forms.CharField(label='Neues Passwort',
                                   widget=forms.PasswordInput)
    new_password_confirm = forms.CharField(
                                   label=u'Neues Passwort (Bestätigung)',
                                   widget=forms.PasswordInput)


class UserCPSettingsForm(forms.Form):
    """
    Form used for the user control panel -- settings
    dialog.
    """
    notify = forms.MultipleChoiceField(
        label='Benachrichtigen per', required=False,
        choices=NOTIFY_BY_CHOICES,
        widget=forms.CheckboxSelectMultiple)
    notifications = forms.MultipleChoiceField(
        label=u'Benachrichtigen bei', required=False,
        choices=NOTIFICATION_CHOICES,
        widget=forms.CheckboxSelectMultiple)
    timezone = forms.ChoiceField(label='Zeitzone', required=True,
        choices=zip(TIMEZONES, TIMEZONES))
    hide_profile = forms.BooleanField(label='Online-Status verstecken',
                                      required=False)
    hide_avatars = forms.BooleanField(label='Avatare ausblenden',
                                      required=False)
    hide_signatures = forms.BooleanField(label='Signaturen ausblenden',
                                         required=False)
    autosubscribe = forms.BooleanField(required=False,
                        label='Thema bei Antwort automatisch abonnieren')
    show_preview = forms.BooleanField(required=False,
        label='Anhang-Vorschau im Forum aktivieren')
    show_thumbnails = forms.BooleanField(required=False,
        label='Bilder-Vorschau ebenfalls aktivieren',
        help_text='automatisch deaktiviert, wenn „Anhang-Vorschau“ deaktiviert ist')

    def clean_notify(self):
        data = self.cleaned_data['notify']
        if u'jabber' in data:
            if not current_request.user.jabber:
                raise forms.ValidationError(u'Du musst eine gültige Jabber '
                    u'Adresse <a href="%s">angeben</a>, um unseren Jabber '
                    u'Service nutzen zu können.' % escape(href(
                        'portal', 'usercp', 'profile')))
        return data


class UserCPProfileForm(forms.Form):
    avatar = forms.ImageField(label='Avatar', required=False)
    delete_avatar = forms.BooleanField(label=u'Avatar löschen', required=False)
    email = EmailField(label='E-Mail', required=True)
    jabber = JabberField(label='Jabber', required=False)
    icq = forms.IntegerField(label='ICQ', required=False,
                             min_value=1, max_value=1000000000)
    msn = forms.CharField(label='MSN Messenger', required=False)
    aim = forms.CharField(label='AIM', required=False, max_length=25)
    yim = forms.CharField(label='Yahoo Instant Messenger', required=False,
                         max_length=25)
    skype = forms.CharField(label='Skype', required=False, max_length=25)
    wengophone = forms.CharField(label='WengoPhone', required=False,
                                 max_length=25)
    sip = forms.CharField(label='SIP', required=False, max_length=25)
    show_email = forms.BooleanField(required=False)
    show_jabber = forms.BooleanField(required=False)
    signature = forms.CharField(widget=forms.Textarea, label='Signatur',
                               required=False)
    coordinates = forms.CharField(label='Koordinaten (Länge, Breite)',
                                  required=False, help_text=u'''
    Probleme beim bestimmen der Koordinaten?
    <a href="http://www.fallingrain.com/world/">Suche einfach deinen Ort</a>
    und übernimm die Koordinaten.''')
    location = forms.CharField(label='Wohnort', required=False, max_length=50)
    occupation = forms.CharField(label='Beruf', required=False, max_length=50)
    interests = forms.CharField(label='Interessen', required=False,
                                max_length=100)
    website = forms.URLField(label='Webseite', required=False)
    launchpad = forms.CharField(label=u'Launchpad Nickname', required=False,
                                max_length=50)
    gpgkey = forms.RegexField('^(0x)?[0-9a-f]{8}$(?i)', label=u'GPG-Schlüssel',
                 max_length=10, required=False, help_text=u'''
    Hier kannst du deinen GPG-Key eintragen. Näheres zu diesem Thema
    erfährst du <a href="http://wiki.ubuntuusers.de/GnuPG/Web_of_Trust">im
    Wiki</a>.''')

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

    def clean_coordinates(self):
        coords = self.cleaned_data.get('coordinates', '').strip()
        if not coords:
            return None
        try:
            coords = [float(x.strip()) for x in coords.split(',')]
            if len(coords) != 2:
                raise forms.ValidationError(u'Koordinaten müssen im Format '
                                            u'"Länge, Breite" angegeben werden.')
            lat, long = coords
        except ValueError:
            raise forms.ValidationError(u'Koordinaten müssen Dezimalzahlen sein.')
        if not -90 < lat < 90:
            raise forms.ValidationError(u'Längenmaße müssen zwischen -90 und 90 sein.')
        if not -180 < long < 180:
            raise forms.ValidationError(u'Breitenmaße müssen zwischen -180 und 180 sein.')
        return lat, long


class SearchForm(forms.Form):
    """The search formular"""
    query = forms.CharField(label='Suchbegriffe:', widget=forms.TextInput(attrs={'size':'100'}))
    area = forms.ChoiceField(label='Bereich:', choices=SEARCH_AREA_CHOICES,
                             required=False)
    page = forms.IntegerField(required=False, widget=forms.HiddenInput)
    per_page = forms.IntegerField(required=False, widget=forms.HiddenInput)
    date_begin = forms.DateTimeField(required=False, widget=DateTimeWidget)
    date_end = forms.DateTimeField(required=False, widget=DateTimeWidget)
    sort = forms.ChoiceField(label='Sortieren:', choices=SEARCH_SORT_CHOICES,
        required=False)


class PrivateMessageForm(forms.Form):
    """Form for writing a new private message"""
    recipient = forms.CharField(label=u'Empfänger', required=False,
        help_text="Mehrere Namen mit Semikolon getrennt eingeben.")
    group_recipient = forms.CharField(label=u'Gruppen', required=False,
        help_text="Mehrere Gruppen mit Semikolon getrennt eingeben.")
    subject = forms.CharField(label=u'Betreff',
                              widget=forms.TextInput(attrs={'size': 50}))
    text = forms.CharField(label=u'Text', widget=forms.Textarea)

    def clean(self):
        d = self.cleaned_data
        if 'recipient' in d and 'group_recipient' in d:
            if not d['recipient'].strip() and not d['group_recipient'].strip():
                raise forms.ValidationError(u'Mindestens einen Empfänger angeben.')
        return self.cleaned_data


class DeactivateUserForm(forms.Form):
    """Form for the user control pannel -- deactivate_user view."""
    password_confirmation = forms.CharField(widget=forms.PasswordInput)


class SubscriptionForm(forms.Form):
    #: this is a list of integers of the subscriptions that should get deleted
    delete = forms.MultipleChoiceField()


class UserErrorReportForm(forms.Form):
    title = forms.CharField(label='kurze Beschreibung', max_length=50,
                            widget=forms.TextInput(attrs={'size':50}))
    text = forms.CharField(label=u'ausführliche Beschreibung',
                           widget=forms.Textarea(attrs={'rows': 3}))
    url = forms.URLField(widget=forms.HiddenInput, label=u'Adresse der Seite,'
                                               u' auf der der Fehler auftrat')

    def clean_url(self):
        if not is_safe_domain(self.cleaned_data['url']):
            raise forms.ValidationError(u'Ungültige URL')
        return self.cleaned_data['url']


def _feed_count_cleanup(n):
    COUNTS = (10, 20, 30, 50, 75, 100)
    if n in COUNTS:
        return n
    if n < COUNTS[0]:
        return COUNTS[0]
    for i in range(len(COUNTS)):
        if n < COUNTS[i]:
            return n - COUNTS[i-1] < COUNTS[i] - n and COUNTS[i-1] or COUNTS[i]
    return COUNTS[-1]


class FeedSelectorForm(forms.Form):
    count = forms.IntegerField(initial=20,
                widget=forms.TextInput(attrs={'size': 2, 'maxlength': 3,
                                              'class': 'feed_count'}),
                label=u'Anzahl der Einträge im Feed',
                help_text=u'Die Anzahl wird gerundet, um die Serverlast '
                          u'gering zu halten')
    mode = forms.ChoiceField(choices=(('full',  u'Ganzer Beitrag'),
                                      ('short', u'Nur Einleitung'),
                                      ('title', u'Nur Titel')),
                             widget=forms.RadioSelect(attrs={'class':'radioul'}))

    def clean(self):
        data = self.cleaned_data
        data['count'] = _feed_count_cleanup(data.get('count', 20))
        return data


class ForumFeedSelectorForm(FeedSelectorForm):
    component = forms.ChoiceField(choices=(('*', u''), ('forum', u''),
                                           ('topic', u'')))
    forum = forms.ChoiceField(required=False)

    def clean_forum(self):
        data = self.cleaned_data
        if data.get('component') == 'forum' and not data.get('forum'):
            raise forms.ValidationError(u'Bitte auswählen')
        return data['forum']


class IkhayaFeedSelectorForm(FeedSelectorForm):
    category = forms.ChoiceField(label=u'Kategorie')


class PlanetFeedSelectorForm(FeedSelectorForm):
    pass


class WikiFeedSelectorForm(FeedSelectorForm):
    #: `mode` is never used but needs to be overwritten because of that.
    mode = forms.ChoiceField(required=False)
    page = forms.ChoiceField(label=u'Seitenname', required=False)
