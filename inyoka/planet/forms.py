# -*- coding: utf-8 -*-
"""
    inyoka.planet.forms
    ~~~~~~~~~~~~~~~~~~~

    Formular for suggesting a new article.

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
from django import forms


class SuggestBlogForm(forms.Form):
    """Form to suggest a new blog url for the planet."""
    name = forms.CharField(label=u'Name des Blogs')
    url =  forms.URLField(label=u'URL')
    description = forms.CharField(label=u'Beschreibung',
        widget=forms.Textarea,
        help_text=(u'Die Beschreibung dient dem Ikhaya-Team '
              u'sich einen besseren Überblick zu verschaffen.'))
