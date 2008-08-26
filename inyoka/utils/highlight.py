# -*- coding: utf-8 -*-
"""
    inyoka.utils.highlight
    ~~~~~~~~~~~~~~~~~~~~~~

    Various functions for highlighting code using pygments.

    :copyright: Copyright 2007 by Benjamin Wiegand, Christoph Hack.
    :license: GNU GPL.
"""
from pygments import highlight
from pygments.lexers import get_lexer_by_name, get_lexer_for_filename, \
    get_lexer_for_mimetype, TextLexer
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound
from pygments.styles.friendly import FriendlyStyle


_pygments_formatter = HtmlFormatter(style='colorful', cssclass='syntax',
                                    linenos='table')


def highlight_code(code, lang=None, filename=None, mimetype=None):
    """Highlight a block using pygments to HTML."""
    try:
        lexer = None
        guessers = [(lang, get_lexer_by_name),
            (filename, get_lexer_for_filename),
            (mimetype, get_lexer_for_mimetype)
        ]
        for var, guesser in guessers:
            if var is not None:
                try:
                    lexer = guesser(var, stripnl=False, startinline=True)
                    break
                except ClassNotFound: continue

        if lexer is None:
            lexer = TextLexer(stripnl=False)
    except LookupError:
        lexer = TextLexer(stripnl=False)
    return highlight(code, lexer, _pygments_formatter)


class HumanStyle(FriendlyStyle):
    """
    This is a pygments style that matches the ubuntuusers design.
    """
