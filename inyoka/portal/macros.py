# -*- coding: utf-8 -*-
"""
    inyoka.portal.macros
    ~~~~~~~~~~~~~~~~~~~~

    The Jinja Template macros of the portal.

    :copyright: Copyright 2007 by Benjamin Wiegand, Christopher Grebs.
    :license: GNU GPL.
"""
from inyoka.utils.templating import partial_renderable


@partial_renderable('portal/_render_form.html')
def render_form(form, *fields, **kwargs):
    inline = kwargs.get('inline', False)
    last = kwargs.get('last', False) and inline
    return {
        'last': last,
        'inline': inline,
        'form':   form,
        'fields': fields
    }


@partial_renderable('portal/_validation_errors.html')
def field_errors(errors):
    """Render an error dict to HTML"""
    return {'errors': errors}


@partial_renderable('portal/_login_form.html')
def render_login_form(form):
    return {'form': form}


@partial_renderable('portal/_registration_form.html')
def render_register_form(form):
    return {'form': form}


@partial_renderable('portal/_lost_password_form.html')
def render_lost_password_form(form):
    return {'form': form}


@partial_renderable('portal/usercp/_change_password_form.html')
def render_change_password_form(form):
    return {'form': form}
