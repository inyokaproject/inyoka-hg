# -*- coding: utf-8 -*-
"""
    inyoka.planet.forms
    ~~~~~~~~~~~~~~~~~~~

    Formular for suggesting a new article.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from django import forms


class SuggestBlogForm(forms.Form):
    """Form to suggest a new blog url for the planet."""
    name = forms.CharField(label=u'Name des Blogs')
    url =  forms.URLField(label=u'URL')
    feed_url =  forms.URLField(label=u'Feed-URL', required=False)
    description = forms.CharField(label=u'Beschreibung',
        widget=forms.Textarea,
        help_text=(u'Die Beschreibung dient dem Ikhaya-Team '
              u'sich einen besseren Überblick zu verschaffen.'))
    mine = forms.BooleanField(label=u'Dieser Blog ist mein eigener',
                              required=False)
    contact_email = forms.EmailField(label=u'E-Mail-Adresse des Autors des '
                                           u'Blogs', required=False)
