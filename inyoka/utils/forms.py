# -*- coding: utf-8 -*-
"""
    inyoka.utils.forms
    ~~~~~~~~~~~~~~~~~~

    This file contains extensions for the django newforms like special form
    fields.

    :copyright: Copyright 2007 by Benjamin Wiegand.
    :license: GNU GPL.
"""
import sys
import md5
from random import randrange
from django import newforms as forms
from django.newforms.widgets import Input
from inyoka.conf import settings
from inyoka.portal.user import User
from inyoka.utils.urls import href
from inyoka.utils.local import current_request


DATETIME_INPUT_FORMATS = (
    '%d.%m.%Y %H:%M', # default output format
    '%d.%m.%Y %H:%M:%S',
    '%d.%m.%y %H:%M',
    '%d.%m.%y %H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%d %H:%M:%S',
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
            return User.objects.get(username=value)
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
    input_type = 'datetime'


class DateWidget(Input):
    input_type = 'date'


class CaptchaField(forms.Field):
    widget = CaptchaWidget

    def clean(self, value):
        solution = current_request.session.get('captcha_solution')
        h = md5.new(settings.SECRET_KEY)
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
