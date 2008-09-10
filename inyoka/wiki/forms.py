# -*- coding: utf-8 -*-
"""
    inyoka.wiki.forms
    ~~~~~~~~~~~~~~~~~

    Contains all the forms we use in the wiki.

    :copyright: Copyright 2007 by Armin Ronacher, Christoph Hack.
    :license: GNU GPL.
"""
from django import forms
from inyoka.wiki.utils import has_conflicts
from inyoka.wiki.acl import test_changes_allowed
from inyoka.wiki.parser import parse, StackExhaused
from inyoka.utils.sessions import SurgeProtectionMixin
from inyoka.utils.urls import href
from inyoka.forum.models import Topic


class PageEditForm(SurgeProtectionMixin, forms.Form):
    """
    Used in the `do_edit` action for both new and existing pages.  The
    following fields are available:

    `text`
        The text of the page as textarea.

    `note`
        A textfield for the change note.
    """
    text = forms.CharField(widget=forms.Textarea(attrs={'rows':20, 'cols':50}))
    note = forms.CharField(max_length=512, required=False,
                           widget=forms.TextInput(attrs={'size': 50}))

    def __init__(self, user=None, page_name=None, old_text=None, data=None):
        forms.Form.__init__(self, data)
        self.user = user
        self.page_name = page_name
        self.old_text = old_text

    def clean_text(self):
        if 'text' not in self.cleaned_data:
            return
        try:
            tree = parse(self.cleaned_data['text'], catch_stack_errors=False)
        except StackExhaused:
            raise forms.ValidationError(u'Im Text befinden sich zu tief '
                                        u'verschachtelte Elemente.')
        if has_conflicts(tree):
            raise forms.ValidationError(u'Im Text befinden sich Konflikt '
                                        u'Markierungen.')
        elif self.user is not None and not \
             test_changes_allowed(self.user, self.page_name, self.old_text,
                                  self.cleaned_data['text']):
            raise forms.ValidationError(u'Du hast Änderungen vorgenommen, '
                                        u'die dir durch die Zugriffsrechte '
                                        u'verwehrt werden.')
        return self.cleaned_data['text']


class AddAttachmentForm(forms.Form):
    """
    Allows the user to upload new attachments.  It's used in the `do_attach`
    action and provides the following fields:

    `attachment`
        A file field for the uploaded file.

    `filename`
        The target filename.  If this is left blank the original filename
        is used for the server too.

    `override`
        A checkbox for the override flag.  If this is true a filename with
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


class EditAttachmentForm(forms.Form):
    """
    A form for editing existing Attachments.  For a more detailed
    description, have a look at the AddAttachmentForm.
    """
    attachment = forms.FileField(required=False)
    text = forms.CharField(label='Description', widget=forms.Textarea,
                           required=False)
    note = forms.CharField(max_length=512, required=False)


class ManageDiscussionForm(forms.Form):
    """Let the user set an existing thread as discussion of a page"""
    topic = forms.CharField(label='Slug des Themas', max_length=50,
        help_text=u'Den Slug eines Themas findest du in der URL (z. B. <var>'
        u'beispiel</var> bei <em>%s</em>)' % href('forum', 'topic', 'beispiel'))

    def clean_topic(self):
        d = self.cleaned_data
        topic = Topic.query.filter_by(slug=d['topic']).first()
        if topic is None:
            raise forms.ValidationError(u'Dieses Thema existiert nicht!')
        return topic


