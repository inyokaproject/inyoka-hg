# -*- coding: utf-8 -*-
"""
    inyoka.utils.highlight
    ~~~~~~~~~~~~~~~~~~~~~~

    Various functions for highlighting code using pygments.

    :copyright: Copyright 2007 by Benjamin Wiegand, Christoph Hack.
    :license: GNU GPL.
"""
from pygments import highlight
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
from pygments.formatters import HtmlFormatter
from pygments.styles.friendly import FriendlyStyle


_pygments_formatter = HtmlFormatter(style='colorful', cssclass='syntax',
                                    linenos='table')


def highlight_code(code, lang=None, filename=None):
    """Highlight a block using pygments to HTML."""
    try:
        if lang is not None:
            lexer = get_lexer_by_name(lang, stripnl=False)
        elif filename is not None:
            lexer = get_lexer_for_filename(filename, stripnl=False)
        else:
            return
    except LookupError:
        return
    return highlight(code, lexer, _pygments_formatter)


class HumanStyle(FriendlyStyle):
    """
    This is a pygments style that matches the ubuntuusers design.
    """
