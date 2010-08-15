# -*- coding: utf-8 -*-
"""
    inyoka.ikhaya.forms
    ~~~~~~~~~~~~~~~~~~~

    Forms for the Ikhaya.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
from django import forms


class SuggestArticleForm(forms.Form):
    title = forms.CharField(label=u'Titel')
    intro = forms.CharField(label=u'Einleitung',
                            widget=forms.Textarea({'rows': 3}))
    text = forms.CharField(label=u'Text', widget=forms.Textarea)
    notes = forms.CharField(label=u'Anmerkungen', widget=forms.Textarea)


class EditCommentForm(forms.Form):
    text = forms.CharField(label=u'Text', widget=forms.Textarea,
             help_text=u'Um dich auf einen anderen Kommentar zu beziehen, '
               u'kannst du <code>@kommentarnummer</code> verwenden.<br />'
               u'Dies wird automatisch eingefügt, wenn du bei einem Beitrag '
               u'auf „Antworten“ klickst.')
