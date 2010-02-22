# -*- coding: utf-8 -*-
"""
    inyoka.forum.forms
    ~~~~~~~~~~~~~~~~~~

    Forms for the forum.

    :copyright: 2007-2008 by Maximilian Trescher, Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
import operator
from django import forms
from inyoka.utils.forms import MultiField
from inyoka.forum.models import UBUNTU_VERSIONS, UBUNTU_DISTROS, Topic, Forum
from inyoka.utils.sessions import SurgeProtectionMixin


VERSION_CHOICES = [('', 'Version auswählen')] + \
                  [(v.number, str(v)) for v in filter(lambda v: v.active, UBUNTU_VERSIONS)]
DISTRO_CHOICES = [('', 'Distribution auswählen')] + UBUNTU_DISTROS.items()
DISTRO_CHOICES.sort(key=operator.itemgetter(0))


class NewPostForm(SurgeProtectionMixin, forms.Form):
    """
    Allows the user to create a new post.  It provides the following fields:
    `text`
        The text for the post.
    `is_plaintext`
        The text is never rendered through our syntax parser
    It's generally used together with `AddAttachmentForm`.
    """
    text = forms.CharField(widget=forms.Textarea)
    is_plaintext = forms.BooleanField(required=False)

    def clean_text(self):
        text = self.cleaned_data.get('text', '')
        if not text.strip():
            raise forms.ValidationError('Text darf nicht leer sein')
        return text


class EditPostForm(forms.Form):
    """
    Allows the user to edit the text of a post.
    This form takes the additional keyword argument `is_first_post`.
    It's generally used together with `AddAttachmentForm`.
    """
    text = forms.CharField(widget=forms.Textarea)
    # the following fields only appear if the post is the first post of the
    # topic.
    #: the user can select, whether the post's topic should be sticky or not.
    sticky = forms.BooleanField(required=False)
    title = forms.CharField(widget=forms.TextInput(attrs={'size':60}))
    ubuntu_version = forms.ChoiceField(choices=VERSION_CHOICES,
                                                required=False)
    ubuntu_distro = forms.ChoiceField(choices=DISTRO_CHOICES, required=False)
    is_plaintext = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        self.is_first_post = kwargs.pop('is_first_post', False)
        forms.Form.__init__(self, *args, **kwargs)

    def clean(self):
        data = self.cleaned_data
        if not self.is_first_post:
            for k in ['sticky', 'title', 'ubuntu_version', 'ubuntu_distro']:
                self._errors.pop(k, None)
        return data


class NewTopicForm(SurgeProtectionMixin, forms.Form):
    """
    Allows the user to create a new topic.
    It provides the following fields:
    `title`
        The title of the topic.
    `text`
        The text of the first post inside the topic.
    `polls`
        A list of new polls bound to this topic.
    `ubuntu_version`
        The ubuntu version the user has.
    `ubuntu_distro`
        The ubuntu distribution the user has.
    `is_plaintext`
        The post is never rendered through our syntax parser
    It's used together with `AddAttachmentForm` in general.
    """
    title = forms.CharField(widget=forms.TextInput(attrs={'size':60}),
                            max_length=100)
    text = forms.CharField(widget=forms.Textarea)
    ubuntu_version = forms.ChoiceField(choices=VERSION_CHOICES,
                                                required=False)
    ubuntu_distro = forms.ChoiceField(choices=DISTRO_CHOICES, required=False)
    sticky = forms.BooleanField(required=False)
    is_plaintext = forms.BooleanField(required=False)

    def clean_text(self):
        text = self.cleaned_data.get('text', '')
        if not text.strip():
            raise forms.ValidationError('Text darf nicht leer sein')
        return text

    def clean_title(self):
        title = self.cleaned_data.get('title', '')
        if not title.strip():
            raise forms.ValidationError('Titel darf nicht leer sein')
        return title

    def clean_ubuntu_version(self):
        ubuntu_version = self.cleaned_data.get('ubuntu_version', None)
        if self.force_version and not ubuntu_version:
            raise forms.ValidationError(forms.fields.Field.
                                        default_error_messages['required'])
        return ubuntu_version

    def clean_ubuntu_distro(self):
        ubuntu_distro = self.cleaned_data.get('ubuntu_distro', None)
        if self.force_version and not ubuntu_distro:
            raise forms.ValidationError(forms.fields.Field.
                                        default_error_messages['required'])
        return ubuntu_distro

    def __init__(self, *args, **kwargs):
        self.force_version = kwargs.pop('force_version', False)
        forms.Form.__init__(self, *args, **kwargs)


class MoveTopicForm(forms.Form):
    """
    This form gives the user the possibility to select a new forum for a
    topic.
    """
    forum_id = forms.ChoiceField(widget=forms.Select(attrs=
        {'class':'firstletterselect'}))


class SplitTopicForm(forms.Form):
    """
    This form used on the split topic page gives the user the choice whether
    the posts should be moved into an existing or a new topic.
    """
    action = forms.ChoiceField(choices=(('add', ''), ('new', '')))
    #: the title of the new topic
    title = forms.CharField(max_length=200)
    #: the forum of the new topic
    forum = forms.ChoiceField()
    #: the slug of the existing topic
    topic = forms.CharField(max_length=200)
    #: this is a boolean that is True if the user wants to select single posts
    #: for splitting out of the topic.
    select_selected = forms.BooleanField(required=False)
    #: this is the list of post ids the user selected manually.
    #: if `select_following` is True, it's ignored if `select` is empty.
    select = forms.MultipleChoiceField()
    #: this is a boolean that is True if the user wants to split out all posts
    #: newer than a specific post.
    select_following = forms.BooleanField(required=False)
    #: this is the first post the user wants to get splitted out of the topic.
    #: All posts following are selected too automatically.
    #: It's ignored if `start` is empty if `select_selected` is True.
    start = forms.ChoiceField()
    #: version info. defaults to the values set in the old topic.
    ubuntu_version = forms.ChoiceField(choices=VERSION_CHOICES,
                                                required=False)
    ubuntu_distro = forms.ChoiceField(choices=DISTRO_CHOICES, required=False)

    def clean(self):
        data = self.cleaned_data
        if data['select_selected']:
            self._errors.pop('start', None)
        elif data['select_following']:
            self._errors.pop('select', None)
        if data.get('action') == 'new':
            self._errors.pop('topic', None)
        elif data.get('action') == 'add':
            self._errors.pop('title', None)
            self._errors.pop('forum', None)
        return data

    def clean_topic(self):
        slug = self.cleaned_data.get('topic')
        if slug:
            t = Topic.query.filter_by(slug=slug).first()
            if not t:
                raise forms.ValidationError(u'Ein Thema mit diesem Slug '
                                            u'existiert nicht')
            return t
        return slug

    def clean_forum(self):
        id = self.cleaned_data.get('forum')
        if id:
            return Forum.query.filter_by(id=id).first()


class AddAttachmentForm(forms.Form):
    """
    Allows the user to upload new attachments.  It provides the following fields:
    `attachment`
        A file field for the uploaded file.

    `filename`
        The target filename.  If this is left blank the original filename
        is used for the server too.

    `override`
        A checkbox for the override flag.  If this is true a filename with
        the same name is overridden (A new revision is created)

    `description`
        The description of the attachment as textarea.
    """
    attachment = forms.FileField(required=True)
    filename = forms.CharField(max_length=512, required=False)
    override = forms.BooleanField(required=False)
    comment = forms.CharField(label='Beschreibung', required=False,
                  widget=forms.TextInput(attrs={'size':'60'}))


class AddPollForm(forms.Form):
    question = forms.CharField(max_length=250, widget=forms.TextInput(attrs={'size':'60'}))
    multiple = forms.BooleanField(required=False)
    options = MultiField((forms.CharField(max_length=250, widget=forms.TextInput(attrs={'size':'50'})),))
    duration = forms.IntegerField(min_value=1, max_value=3650, required=False,
                                  widget=forms.TextInput(attrs={'size':'3'}))


class ReportTopicForm(forms.Form):
    """
    Allows the user to report the moderators a topic.
    It's only field is a text field where the user can write why he thinks
    that the moderators should have a look at this topic.
    """
    text = forms.CharField(label='Begründung', widget=forms.Textarea)


class ReportListForm(forms.Form):
    """
    This form lets the moderator select a bunch of topics for removing the
    reported flag.
    """
    selected = forms.MultipleChoiceField()
