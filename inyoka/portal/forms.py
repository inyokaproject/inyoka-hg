# -*- coding: utf-8 -*-
"""
    inyoka.portal.forms
    ~~~~~~~~~~~~~~~~~~~

    Various forms for the portal.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import Image
from django import forms
from django.utils.safestring import mark_safe
from django.db import connection
from django.utils.translation import ugettext as _

from inyoka.conf import settings
from inyoka.forum.forms import UBUNTU_VERSIONS
from inyoka.forum.acl import filter_invisible
from inyoka.forum.models import Forum
from inyoka.utils.dates import datetime_to_timezone
from inyoka.utils.user import is_valid_username
from inyoka.utils.dates import TIMEZONES
from inyoka.utils.urls import href, is_safe_domain
from inyoka.utils.forms import CaptchaField, DateTimeWidget, \
                               HiddenCaptchaField, EmailField, JabberField
from inyoka.utils.local import current_request
from inyoka.utils.html import escape
from inyoka.utils.storage import storage
from inyoka.utils.sessions import SurgeProtectionMixin
from inyoka.utils.search import search as search_system
from inyoka.portal.user import User
from inyoka.wiki.parser import validate_signature, SignatureError

#: Some constants used for ChoiceFields
NOTIFY_BY_CHOICES = (
    ('mail', 'E-Mail'),
    ('jabber', 'Jabber'),
)

NOTIFICATION_CHOICES = (
    ('topic_move', 'Verschieben eines abonnierten Themas'),
    ('topic_split', 'Aufteilen eines abonnierten Themas'),
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

VERSION_CHOICES = [(v.number, str(v)) for v in UBUNTU_VERSIONS if v.active]

SEARCH_AREAS = {
    'wiki': 'w',
    'forum': 'f',
    'ikhaya': 'i',
    'planet': 'p'
}


class LoginForm(forms.Form):
    """Simple form for the login dialog"""
    username = forms.CharField(label='Benutzername oder E-Mail-Adresse')
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
    username = forms.CharField(label='Benutzername', max_length=20)
    email = EmailField(label='E-Mail', help_text=u'Wir benötigen deine '
        u'E-Mail-Adresse, um dir ein neues Passwort zu schicken, falls du '
        u'es vergessen haben solltest. Sie ist für andere Benutzer nicht '
        u'sichtbar. ubuntuusers.de <a href="%s">garantiert</a>, dass sie '
        u'nicht weitergegeben wird.' % href('portal', 'datenschutz'))
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
        username = self.cleaned_data['username']
        if not is_valid_username(username):
            raise forms.ValidationError(
                u'Dein Benutzername enthält nicht benutzbare Zeichen; es sind nur alphanumerische Zeichen sowie „-“ und „ “ erlaubt.'
            )
        try:
            user = User.objects.get(username)
        except User.DoesNotExist:
            # To bad we had to change the user regex…,  we need to rename users fast…
            c = connection.cursor()
            c.execute("SELECT COUNT(*) FROM portal_user WHERE username LIKE %s", [username.replace(' ', '%')])
            count = c.fetchone()[0]
            if count == 0:
                return username

        raise forms.ValidationError(
            u'Der Benutzername ist leider schon vergeben. '
            u'Bitte wähle einen anderen.'
        )

    def clean(self):
        """
        Validates that the two password inputs match.
        """
        if 'password' in self.cleaned_data and 'confirm_password' in self.cleaned_data:
            if self.cleaned_data['password'] == self.cleaned_data['confirm_password']:
                return self.cleaned_data
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
        try:
            user = User.objects.get(email__iexact=self.cleaned_data['email'])
        except User.DoesNotExist:
            return self.cleaned_data['email']

        raise forms.ValidationError(mark_safe(
            u'Die angegebene E-Mail-Adresse wird bereits benutzt!'
            u' Falls du dein Passwort vergessen hast, kannst du es '
            u'<a href="%s">wiederherstellen lassen</a>' % escape(
                href('portal', 'lost_password')))
        )


class LostPasswordForm(forms.Form):
    """
    Form for the lost password form.

    It's similar to the register form and uses
    a hidden and a visible image CAPTCHA too.
    """
    username = forms.CharField(label=u'Benutzername oder E-Mail-Adresse')
    captcha = CaptchaField(label='CAPTCHA')
    hidden_captcha = HiddenCaptchaField(required=False)

    def clean_username(self):
        data = super(LostPasswordForm, self).clean()
        if 'username' in data and '@' in data['username']:
            try:
                self.user = User.objects.get(email=data['username'])
            except User.DoesNotExist:
                raise forms.ValidationError(
                    u'Einen Benutzer mit der E-Mail-Adresse „%s“ '
                    u'gibt es nicht!' % data['username']
                )
        else:
            try:
                self.user = User.objects.get(data['username'])
            except User.DoesNotExist:
                raise forms.ValidationError(
                    _(u'User “%s” does not exist!') % data['username']
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
            data['user'] = User.objects.get(self['username'].data,
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
    Form used for the user control panel – dialog.
    """
    notify = forms.MultipleChoiceField(
        label='Benachrichtigen per', required=False,
        choices=NOTIFY_BY_CHOICES,
        widget=forms.CheckboxSelectMultiple)
    notifications = forms.MultipleChoiceField(
        label=u'Benachrichtigen bei', required=False,
        choices=NOTIFICATION_CHOICES,
        widget=forms.CheckboxSelectMultiple)
    ubuntu_version = forms.MultipleChoiceField(
        label='Benachrichtigung bei neuen Topics mit bestimmter Ubuntu Version',
        required=False, choices=VERSION_CHOICES,
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
    highlight_search = forms.BooleanField(required=False,
        label='Suchwörter hervorheben',
        help_text='Suchwörter werden in gelber Farbe hervorgehoben')
    mark_read_on_logout = forms.BooleanField(required=False,
        label=u'Automatisch alle Foren beim Abmelden als gelesen markieren')


    def clean_notify(self):
        data = self.cleaned_data['notify']
        if u'jabber' in data:
            if not current_request.user.jabber:
                raise forms.ValidationError(mark_safe(u'Du musst eine gültige Jabber '
                    u'Adresse <a href="%s">angeben</a>, um unseren Jabber '
                    u'Service nutzen zu können.' % escape(href(
                        'portal', 'usercp', 'profile'))))
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
    coordinates = forms.CharField(label='Koordinaten (Breite, Länge)',
                                  required=False, help_text=u'''
    Probleme beim bestimmen der Koordinaten?
    <a href="http://www.fallingrain.com/world/">Suche einfach deinen Ort</a>
    und übernimm die Koordinaten.''')
    location = forms.CharField(label='Wohnort', required=False, max_length=50)
    occupation = forms.CharField(label='Beruf', required=False, max_length=50)
    interests = forms.CharField(label='Interessen', required=False,
                                max_length=100)
    website = forms.URLField(label='Webseite', required=False)
    launchpad = forms.CharField(label=u'Launchpad-Benutzername', required=False,
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

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if not email:
            raise forms.ValidationError(u'Keine Email-Adresse angegeben!')
        try:
            other_user = User.objects.get(email=email)
        except User.DoesNotExist:
            return email
        else:
            if other_user.id != current_request.user.id:
                raise forms.ValidationError(u'Diese E-Mail-Adresse wird schon verwendet!')
            return email

    def clean_avatar(self):
        """
        Keep the user form setting avatar to a too big size.
        """
        data = self.cleaned_data
        if data['avatar'] is None:
            return
        st = int(storage.get('max_avatar_size', 0))
        if st and data['avatar'].size > st * 1024:
            raise forms.ValidationError(
                u'Der von dir ausgewählte Avatar konnte nicht '
                u'hochgeladen werden, da er zu groß ist. Bitte '
                u'wähle einen anderen Avatar.')
        try:
            image = Image.open(data['avatar'])
        finally:
            data['avatar'].seek(0)
        max_size = (
            int(storage.get('max_avatar_width', 0)),
            int(storage.get('max_avatar_height', 0)))
        if any(length > max_length for max_length, length in zip(max_size, image.size)):
            raise forms.ValidationError(
                u'Der von dir ausgewählte Avatar konnte nicht '
                u'hochgeladen werden, da er zu groß ist. Bitte '
                u'wähle einen anderen Avatar.')
        return data['avatar']



class SearchForm(forms.Form):
    """The search formular"""

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        forms.Form.__init__(self, *args, **kwargs)

        self.fields['forums'].choices = [('support', u'Alle Support-Foren'),
            ('all', u'Alle Foren')]
        forums = filter_invisible(self.user, Forum.query.get_cached())
        for offset, forum in Forum.get_children_recursive(forums):
            self.fields['forums'].choices.append((forum.slug, u'  ' * offset + forum.name))

    query = forms.CharField(label='Suchbegriffe:', widget=forms.TextInput)
    area = forms.ChoiceField(label='Bereich:', choices=SEARCH_AREA_CHOICES,
                      required=False, widget=forms.RadioSelect, initial='all')
    page = forms.IntegerField(required=False, widget=forms.HiddenInput)
    per_page = forms.IntegerField(required=False, widget=forms.HiddenInput)
    date_begin = forms.DateTimeField(required=False, widget=DateTimeWidget)
    date_end = forms.DateTimeField(required=False, widget=DateTimeWidget)
    sort = forms.ChoiceField(label='Sortieren:', choices=SEARCH_SORT_CHOICES,
        required=False)
    forums = forms.ChoiceField(label=u'Foren', initial='support',
        required=False)
    show_wiki_attachments = forms.BooleanField(label='Zeige Dateianhänge',
        required=False)

    def clean_area(self):
        # Select all areas when no area was specified explicitely
        return self.cleaned_data.get('area') or 'all'

    def search(self):
        """Performs the actual query and return the results"""
        d = self.cleaned_data

        query = d['query']

        exclude = []

        # we use per default the support-forum filter
        if not d['forums']:
            d['forums'] = 'support'

        if d['area'] in ('forum', 'all') and d['forums'] and \
                d['forums'] not in ('support', 'all'):
            query += ' category:"%s"' % d['forums']
        elif d['forums'] == 'support':
            exclude = list(settings.SEARCH_DEFAULT_EXCLUDE)

        if not d['show_wiki_attachments']:
            exclude.append('C__attachment__')

        return search_system.query(self.user,
            query,
            page=d['page'] or 1,
            per_page=d['per_page'] or 20,
            date_begin=datetime_to_timezone(d['date_begin'], enforce_utc=True),
            date_end=datetime_to_timezone(d['date_end'], enforce_utc=True),
            component=SEARCH_AREAS.get(d['area']),
            exclude=exclude,
            sort=d['sort']
        )



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

class PrivateMessageFormProtected(SurgeProtectionMixin, PrivateMessageForm):
    source_protection_timeout = 60 * 5


class DeactivateUserForm(forms.Form):
    """Form for the user control panel -- deactivate_user view."""
    password_confirmation = forms.CharField(widget=forms.PasswordInput)


class SubscriptionForm(forms.Form):
    #: this is a list of integers of the subscriptions
    select = forms.MultipleChoiceField()


class PrivateMessageIndexForm(forms.Form):
    #: this is a list of integers of the pms that should get deleted
    delete = forms.MultipleChoiceField()


class UserErrorReportForm(forms.Form):
    title = forms.CharField(label='kurze Beschreibung', max_length=50,
                            widget=forms.TextInput(attrs={'size':50}))
    text = forms.CharField(label=u'ausführliche Beschreibung',
                           widget=forms.Textarea(attrs={'rows': 3}))
    url = forms.URLField(widget=forms.HiddenInput, required=False,
                         label=u'Adresse der Seite, auf die sich das Ticket bezieht')

    def clean_url(self):
        data = self.cleaned_data
        if data.get('url') and not is_safe_domain(self.cleaned_data['url']):
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
    mode = forms.ChoiceField(initial='short',
        choices=(('full',  u'Ganzer Beitrag'),
                 ('short', u'Nur Einleitung'),
                 ('title', u'Nur Titel')),
        widget=forms.RadioSelect(attrs={'class':'radioul'}))

    def clean(self):
        data = self.cleaned_data
        data['count'] = _feed_count_cleanup(data.get('count', 20))
        return data


class ForumFeedSelectorForm(FeedSelectorForm):
    component = forms.ChoiceField(initial='forum',
        choices=(('*', u''), ('forum', u''), ('topic', u'')))
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
    page = forms.CharField(label=u'Seitenname', required=False,
                           help_text=(u'Wenn nicht angegeben, werden die letzten '
                                 u'Änderungen angezeigt'))
