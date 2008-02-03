# -*- coding: utf-8 -*-
"""
    inyoka.utils.forms
    ~~~~~~~~~~~~~~~~~~

    This file contains extensions for the django newforms like special form
    fields.

    :copyright: Copyright 2007 by Benjamin Wiegand.
    :license: GNU GPL.
"""
from django import newforms as forms
import django.db.models.base
from inyoka.portal.user import User


DATETIME_INPUT_FORMATS = (
    '%d.%m.%Y %H:%M', # default output format
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%d.%m.%Y %H:%M:%S',
    '%d.%m.%Y %H:%M',
    '%d.%m.%y %H:%M:%S',
    '%d.%m.%y %H:%M',
    '%Y-%m-%d, %H:%M:%S',
    '%Y-%m-%d, %H:%M',
    '%d.%m.%Y, %H:%M:%S',
    '%d.%m.%Y, %H:%M',
    '%d.%m.%y, %H:%M:%S',
    '%d.%m.%y, %H:%M',
)


class EmptyTextInput(forms.TextInput):

    def render(self, name, value, attrs=None):
        return super(EmptyTextInput, self).render(name, u'', attrs)


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
