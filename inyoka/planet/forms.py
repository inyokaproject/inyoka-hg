# -*- coding: utf-8 -*-
"""
    inyoka.planet.forms
    ~~~~~~~~~~~~~~~~~~~

    Formular for suggesting a new article.

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
from django import newforms as forms


class SuggestBlogForm(forms.Form):
    """Form to suggest a new blog url for the planet."""
    name = forms.CharField(label=u'Name')
    url =  forms.URLField(label=u'URL')
    description = forms.CharField(label=u'Beschreibung',
                                  widget=forms.Textarea)
