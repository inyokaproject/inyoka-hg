# -*- coding: utf-8 -*-
"""
    inyoka.wiki.forms
    ~~~~~~~~~~~~~~~~~

    Contains all the forms we use in the wiki.

    :copyright: Copyright 2007 by Armin Ronacher, Christoph Hack.
    :license: GNU GPL.
"""
from django import newforms as forms
from inyoka.wiki.utils import has_conflicts


class PageEditForm(forms.Form):
    """
    Used in the `do_edit` action for both new and existing pages. The
    following fields are available:

    `text`
        The text of the page as textarea.

    `note`
        A textfield for the change note.
    """
    text = forms.CharField(widget=forms.Textarea(attrs={'rows':20, 'cols':50}))
    note = forms.CharField(max_length=512, required=False,
                           widget=forms.TextInput(attrs={'size': 50}))

    def clean_text(self):
        if 'text' in self.cleaned_data:
            if has_conflicts(self.cleaned_data['text']):
                raise forms.ValidationError(u'Im Text befinden sich Konflikt '
                                            u'Markierungen.')
            return self.cleaned_data['text']


class AddAttachmentForm(forms.Form):
    """
    Allows the user to upload new attachments. It's used in the `do_attach`
    action and provides the following fields:

    `attachment`
        A file field for the uploaded file.

    `filename`
        The target filename. If this is left blank the original filename
        is used for the server too.

    `override`
        A checkbox for the override flag. If this is true a filename with
        the same name is overridden (A new revision is created)

    `text`
        The description of the attachment as textarea.

    `note`
        A textfield for the change note.
    """
    attachment = forms.FileField(required=True)
    filename = forms.CharField(max_length=512, required=False)
    override = forms.BooleanField(required=False)
    text = forms.CharField(label='Description', widget=forms.Textarea,
                           required=False)
    note = forms.CharField(max_length=512, required=False)
