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
