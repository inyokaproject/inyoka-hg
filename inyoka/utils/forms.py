# -*- coding: utf-8 -*-
"""
    inyoka.utils.forms
    ~~~~~~~~~~~~~~~~~~

    This file contains extensions for the django forms like special form
    fields.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import sys
from hashlib import md5
from random import randrange
from django import forms
from django.forms.widgets import Input
from inyoka.conf import settings
from inyoka.portal.user import User
from inyoka.utils.urls import href
from inyoka.utils.local import current_request
from inyoka.utils.mail import may_be_valid_mail, is_blocked_host
from inyoka.utils.jabber import may_be_valid_jabber
from inyoka.utils.flashing import flash
from inyoka.utils.text import slugify


DATETIME_INPUT_FORMATS = (
    '%d.%m.%Y %H:%M', # default output format
    '%d.%m.%Y %H:%M:%S',
    '%d.%m.%y %H:%M',
    '%d.%m.%y %H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%dT%H:%MZ',
    '%Y-%m-%d, %H:%M',
    '%Y-%m-%d, %H:%M:%S',
    '%d.%m.%Y, %H:%M',
    '%d.%m.%Y, %H:%M:%S',
    '%d.%m.%y, %H:%M',
    '%d.%m.%y, %H:%M:%S',
)

DATE_INPUT_FORMATS = (
    '%d.%m.%Y', # default output format
    '%d.%m.%y',
    '%Y-%m-%d',
)

TIME_INPUT_FORMATS = (
    '%H:%M:%S',
    '%H:%M',
)


class MultiField(forms.Field):
    """
    This field validates a bunch of values using zero, one or more fields.
    If the value is just one string, a list is created.
    """
    widget = forms.SelectMultiple

    def __init__(self, fields=(), *args, **kwargs):
        super(MultiField, self).__init__(*args, **kwargs)
        self.fields = fields

    def clean(self, value):
        """
        Validates that the value is a list or a tuple.
        """
        if not isinstance(value, (list, tuple)):
            value = [value]

        def _clean(part):
            for field in self.fields:
                part = field.clean(part)
            return part

        return [_clean(part) for part in value]


class UserField(forms.CharField):
    """
    Allows to enter a username as text and validates if the given user exists.
    """
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)

    def clean(self, value):
        if not value:
            return
        try:
            return User.objects.get(value)
        except:
            raise forms.ValidationError(u'Diesen Benutzer gibt es nicht')


class CaptchaWidget(Input):
    input_type = 'text'

    def render(self, name, value, attrs=None):
        input = Input.render(self, name, u'', attrs)
        return (u'<img src="%s" class="captcha" alt="Captcha" /><br />'
                u'Bitte gib den Code des obigen Bildes hier ein: <br />%s '
                u'<input type="submit" name="renew_captcha" value="Neuen Code'
                u' erzeugen" />') % (
            href('portal', __service__='portal.get_captcha',
                 rnd=randrange(1, sys.maxint)), input)


class DateTimeWidget(Input):
    input_type = 'text'
    value_type = 'datetime'

    def render(self, name, value, attrs=None):
        if attrs is None:
            attrs = {}
        attrs['valuetype'] = self.value_type
        return Input.render(self, name, value, attrs)


class DateWidget(DateTimeWidget):
    input_type = 'text'
    value_type = 'date'


class TimeWidget(DateTimeWidget):
    input_type = 'text'
    value_type = 'time'


class CaptchaField(forms.Field):
    widget = CaptchaWidget

    def __init__(self, only_anonymous=False, *args, **kwargs):
        self.only_anonymous = only_anonymous
        forms.Field.__init__(self, *args, **kwargs)

    def clean(self, value):
        if current_request.user.is_authenticated and self.only_anonymous:
            return True
        solution = current_request.session.get('captcha_solution')
        if not solution:
            flash(u'Du musst Cookies aktivieren!', False)
        elif value:
            h = md5(settings.SECRET_KEY)
            if isinstance(value, unicode):
                # md5 doesn't like to have non-ascii containing unicode strings
                value = value.encode('utf-8')
            if value:
                h.update(value)
            if h.digest() == solution:
                return True
        raise forms.ValidationError(u'Die Eingabe des Captchas war nicht '
                                    u'korrekt')


class HiddenCaptchaField(forms.Field):
    widget = forms.HiddenInput

    def clean(self, value):
        if not value:
            return True
        else:
            raise forms.ValidationError(u'Du hast ein unsichtbares Feld '
                    u'ausgefüllt und wurdest deshalb als Bot identifiziert.')


class EmailField(forms.CharField):

    def clean(self, value):
        value = super(forms.CharField, self).clean(value)
        value = value.strip()
        if is_blocked_host(value):
            raise forms.ValidationError(u'''
                Die von dir angegebene E-Mail-Adresse gehört zu einem
                Anbieter, den wir wegen Spamproblemen sperren mussten.
                Bitte gebe eine andere Adresse an.
            '''.strip())
        elif not may_be_valid_mail(value):
            raise forms.ValidationError(u'''
                Die von dir angebene E-Mail-Adresse ist ungültig.  Bitte
                überpfüfe die Eingabe.
            '''.strip())
        return value


class JabberField(forms.CharField):

    def clean(self, value):
        if not value:
            return
        value = value.strip()
        if not may_be_valid_jabber(value):
            raise forms.ValidationError(u'''
                Die von dir angegebene Jabber-Adresse ist ungültig.  Bitte
                überprüfe die Eingabe.
            '''.strip())
        return value


class SlugField(forms.CharField):

    def clean(self, value):
        if value:
            value = slugify(value)
            return value.strip() if value else None
        return None
