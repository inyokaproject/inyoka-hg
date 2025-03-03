#-*- coding: utf-8 -*-
"""
    inyoka.utils.css
    ~~~~~~~~~~~~~~~~

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import re


acceptable_css_properties = frozenset([
    'azimuth', 'background-color', 'border-bottom-color',
    'border-collapse', 'border-color', 'border-left-color',
    'border-right-color', 'border-top-color', 'clear', 'color',
    'cursor', 'direction', 'display', 'elevation', 'float', 'font',
    'font-family', 'font-size', 'font-style', 'font-variant',
    'font-weight', 'height', 'letter-spacing', 'line-height', 'overflow',
    'pause', 'pause-after', 'pause-before', 'pitch', 'pitch-range',
    'richness', 'speak', 'speak-header', 'speak-numeral',
    'speak-punctuation', 'speech-rate', 'stress', 'text-align',
    'text-decoration', 'text-indent', 'unicode-bidi', 'vertical-align',
    'voice-family', 'volume', 'white-space', 'width', 'max-width',
])

acceptable_css_keywords = frozenset([
    'auto', 'aqua', 'black', 'block', 'blue', 'bold', 'both', 'bottom',
    'brown', 'center', 'collapse', 'dashed', 'dotted', 'fuchsia',
    'gray', 'green', '!important', 'italic', 'left', 'lime', 'maroon',
    'medium', 'none', 'navy', 'normal', 'nowrap', 'olive', 'pointer',
    'purple', 'red', 'right', 'solid', 'silver', 'teal', 'top',
    'transparent', 'underline', 'white', 'yellow'
])

_css_url_re = re.compile(r'url\s*\(\s*[^\s)]+?\s*\)\s*')
_css_sanity_check_re = re.compile(r'''(?x)
    ^(
        [:,;#%.\sa-zA-Z0-9!]
      |  \w-\w
      | '[\s\w]+'|"[\s\w]+"
      | \([\d,\s]+\)
    )*$
''')
_css_pair_re = re.compile(r'([-\w]+)\s*:\s*([^:;]*)')
_css_unit_re = re.compile(r'''(?x)
    ^(
        #[0-9a-f]+
      | rgb\(\d+%?,\d*%?,?\d*%?\)?
      | \d{0,2}\.?\d{0,2}(cm|em|ex|in|mm|pc|pt|px|%|,|\))?
    )$
''')


def filter_style(css):
    if css is None:
        return None

    css = _css_url_re.sub(u' ', css)
    if _css_sanity_check_re.match(css) is None:
        return u''

    clean = []
    for prop, value in _css_pair_re.findall(css):
        if not value:
            continue
        if prop.lower() in acceptable_css_properties:
            clean.append('%s: %s' % (prop, value))
        elif prop.split('-', 1)[0].lower() in \
             ('background', 'border', 'margin', 'padding'):
            for keyword in value.split():
                if not keyword in acceptable_css_keywords and \
                   not _css_unit_re.match(keyword):
                    break
            else:
                clean.append('%s: %s' % (prop, value))
    return u'; '.join(clean)
