#-*- coding: utf-8 -*-
"""
    inyoka.utils.css
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import re
import xml.dom
import logging
import cssutils
from cssutils.css import CSSStyleDeclaration as CSSStyleDeclarationBase
from cssutils.serialize import CSSSerializer as CSSSerializerBase, \
    Preferences as CSSPreferences, Out
from inyoka.utils.urls import is_safe_domain


cssutils.log.setLevel(logging.NOTSET)

property_list = [
    'border', 'clear', 'float', 'font.*?', 'height', 'line-height',
    'margin.*?', 'max-height', 'max-width', 'min-height', 'min-width',
    'outline.*?', 'overflow', 'padding.*?', 'position', 'quotes', 'size',
    'table-layout', 'text-.*?', 'vertical-align', 'width',
    'color', 'background-color', 'background-image',
]

_url_pattern = (
    # allowed urls with netloc
    r'(?:(?:https?|ftps?|)://)'
)
_url_re = re.compile(r'url\(.*?\)')
_allowed_url_re = re.compile(r'url\([\'"]?(%s[^\s\'"]+)[\'"]?\)' % _url_pattern)
_allowed_properties_re = re.compile(r'|'.join(property_list))


class CSSSerializer(CSSSerializerBase):

    def __init__(self):
        CSSSerializerBase.__init__(self, CSSPreferences(
            keepComments=False, keepAllProperties=True,
            lineSeparator=u''
        ))

    def _valid(self, x):
        if not x.value:
            return False
        elif not _allowed_properties_re.match(x.name):
            return False
        elif _url_re.match(x.value):
            m = _allowed_url_re.match(x.value)
            if not m or not is_safe_domain(m.groups()[0]):
                return False
            return True
        else:
            return True

    def do_css_CSSStyleDeclaration(self, style, separator=None):
        """
        Overload of the CSSSerializer's method to get some
        special behaviour.
        """
        # may be comments only
        if len(style.seq) > 0:
            if separator is None:
                separator = self.prefs.lineSeparator

            if self.prefs.keepAllProperties:
                # all
                seq = style.seq
            else:
                # only effective ones
                _effective = style.getProperties()
                seq = [item for item in style.seq
                         if (isinstance(item.value, cssutils.css.Property)
                             and item.value in _effective)
                         or not isinstance(item.value, cssutils.css.Property)]

            out = Out(cssutils.ser)
            for i, item in enumerate(seq):
                typ, val = item.type, item.value
                if isinstance(val, cssutils.css.CSSComment):
                    # CSSComment
                    out.append(val.cssText, 'COMMENT')
                elif isinstance(val, cssutils.css.Property):
                    out.append(val, 'Property')
                    # PropertySimilarNameList
                    if not (self.prefs.omitLastSemicolon and i==len(seq)-1):
                        out.append(u';')
                elif isinstance(val, cssutils.css.CSSUnknownRule):
                    out.append(val, cssutils.css.CssRule.UNKNOWN_RULE)

            return u''.join(x.strip() for x in out.out).strip('; ')

        else:
            return u''

cssutils.setSerializer(CSSSerializer())


class CSSStyleDeclaration(CSSStyleDeclarationBase):
    def _parse(self, expected, seq, tokenizer, productions, default=None,
               new=None):
        # this method raises a damn SyntaxErr on some property
        # we don't need...
        wellformed = True
        if tokenizer:
            prods = self._adddefaultproductions(productions, new)
            for token in tokenizer:
                p = prods.get(token[0], default)
                if p:
                    try:
                        expected = p(expected, seq, token, tokenizer)
                    except xml.dom.SyntaxErr:
                        wellformed = False
                else:
                    wellformed = False
        return wellformed, expected


def filter_style(css):
    if css is None:
        return None
    sheet = CSSStyleDeclaration(css)
    return sheet.getCssText(u'')
