# -*- coding: utf-8 -*-
"""
    inyoka.forum.macros
    ~~~~~~~~~~~~~~~~~~~

    The Jinja template macros of the forum.

    :copyright: Copyright 2007 by Benjamin Wiegand.
    :license: GNU GPL.
"""
from inyoka.utils.templating import partial_renderable


@partial_renderable('forum/_attachment_form.html')
def attachment_form(form, attachments):
    """Render the formular for uploading new attachments"""
    return {
        'form': form,
        'attachments': attachments
    }


@partial_renderable('forum/_attachments.html')
def render_attachments(attachments):
    """Render the attachments to a nice HTML table"""
    return {
        'attachments': attachments
    }
