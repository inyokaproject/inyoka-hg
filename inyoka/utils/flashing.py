# -*- coding: utf-8 -*-
"""
    inyoka.utils.flashing
    ~~~~~~~~~~~~~~~~~~~~~

    Implements a simple system to flash messages.

    :copyright: Copyright 2007 by Armin Ronacher, Marian Sigler.
    :license: GNU GPL.
"""
from inyoka.middlewares.registry import r


def flash(message, success=None, classifier=None, dialog=False,
          dialog_url=None):
    """
    Flash a message (can contain XHTML).  If ``success`` is True, the flashbar
    will be green, if it's False, it will be red, if it's undefined it will be
    yellow.  If a classifier is given it can be used to unflash all messages
    with that classifier using the `unflash` method.

    It's also possible to flash a simple yes/no dialog through this function.
    So you don't need to create a new template and a new view for very simple
    questions e.g "Do you want to delete this object".
    If you want to use the dialog feature apply ``dialog=True` and use
    ``dialog_url`` to specify an url for submitting the post-form.
    """
    session = getattr(r.request, 'session', None)
    if session is None:
        return False
    if not 'flashed_messages' in session:
        session['flashed_messages'] = [
            (message, success, classifier, dialog, dialog_url)
        ]
    else:
        session['flashed_messages'].append(
            (message, success, classifier, dialog, dialog_url)
        )
        session.modified = True


def unflash(classifier):
    """Unflash all messages with a given classifier"""
    session = getattr(r.request, 'session', None)
    if session is None:
        return
    session['flashed_messages'] = [item for item in session.get(
                                   'flashed_messages', ())
                                   if item[2] != classifier]
    if not session['flashed_messages']:
        del session['flashed_messages']


def clear():
    """Clear the whole flash buffer."""
    session = getattr(r.request, 'session', None)
    if session is not None:
        session.pop('flashed_messages', None)


def get_flashed_messages():
    """Get all flashed messages for this user."""
    flash_buffer = getattr(r.request, 'flash_message_buffer', None)
    if flash_buffer is not None:
        return flash_buffer
    session = getattr(r.request, 'session', None)
    if session is None:
        return []
    flash_buffer = [FlashMessage(x[0], x[1], x[3], x[4]) for x in
                    session.get('flashed_messages', ())]
    session.pop('flashed_messages', None)
    r.request.flash_message_buffer = flash_buffer
    return flash_buffer


class FlashMessage(object):
    __slots__ = ('text', 'success', 'dialog', 'dialog_url')

    def __init__(self, text, success=None, dialog=False, dialog_url=None):
        self.text = text
        self.success = success
        self.dialog = dialog
        self.dialog_url = dialog_url

    def __repr__(self):
        return '<%s(%s:%s:%s)>' % (
            self.__class__.__name__,
            self.text,
            self.success,
            self.dialog and 'dialog' or ''
        )
