# -*- coding: utf-8 -*-
"""
    inyoka.ikhaya.forms
    ~~~~~~~~~~~~~~~~~~~

    Forms for the Ikhaya.

    :copyright: 2007 by Benjamin Wiegand, Marian Sigler.
    :license: GNU GPL, see LICENSE for more details.
"""
from django import newforms as forms


class SuggestArticleForm(forms.Form):
    title = forms.CharField(label=u'Titel')
    intro = forms.CharField(label=u'Einleitung',
                            widget=forms.Textarea({'rows': 3}))
    text = forms.CharField(label=u'Text', widget=forms.Textarea)


class EditCommentForm(forms.Form):
    text = forms.CharField(label=u'Text', widget=forms.Textarea,
             help_text=u'Um dich auf einen anderen Kommentar zu beziehen, '
               u'kannst du <em>@kommentar_nummer</em> verwenden.<br />'
               u'Dies wird automatisch eingefügt, wenn du bei einem Beitrag '
               u'auf „Antworten“ klickst.')
