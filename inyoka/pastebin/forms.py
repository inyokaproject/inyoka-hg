# -*- coding: utf-8 -*-
"""
    inyoka.pastebin.forms
    ~~~~~~~~~~~~~~~~~~~~~

    "Add new paste" formular.

    :copyright: 2007 by Benjamin Wiegand.
    :license: GNU GPL, see LICENSE for more details.
"""
from django import forms
from inyoka.utils.forms import CaptchaField


# languages for highlighting. We do not use the full list of pygments
# lexers because that is just insane ;-)
LANGUAGES = [
    ('text', 'Einfacher Text'),
    ('apache', 'Apache Config (.htaccess)'),
    ('bash', 'Bash'),
    ('bat', 'Batch (.bat)'),
    ('c', 'C'),
    ('csharp', 'C#'),
    ('cpp', 'C++'),
    ('css', 'CSS'),
    ('d', 'D'),
    ('html+django', 'Django / Jinja Templates'),
    ('rhtml', 'eRuby / rhtml'),
    ('html+genshi', 'Genshi Templates'),
    ('haskell', 'Haskell'),
    ('html', 'HTML'),
    ('irc', 'IRC Logs'),
    ('java', 'Java'),
    ('js', 'JavaScript'),
    ('jsp', 'JSP'),
    ('lua', 'Lua'),
    ('html+mako', 'Mako Templates'),
    ('minid', 'MiniD'),
    ('html+myghty', 'Myghty Templates'),
    ('ocaml', 'OCaml'),
    ('perl', 'Perl'),
    ('html+php', 'PHP'),
    ('python', 'Python'),
    ('pycon', 'Python Console Sessions'),
    ('pytb', 'Python Tracebacks'),
    ('rst', 'reStructuredText'),
    ('ruby', 'Ruby'),
    ('scheme', 'Scheme'),
    ('smarty', 'Smarty'),
    ('sourceslist', 'sources.list'),
    ('sql', 'SQL'),
    ('squidconf', 'SquidConf'),
    ('tex', 'TeX / LaTeX'),
    ('diff', 'Unified Diff'),
    ('vim', 'Vim Scripts'),
    ('xml', 'XML')
]


class AddPasteForm(forms.Form):
    title = forms.CharField(max_length=40, required=False, label='Titel')
    language = forms.ChoiceField(widget=forms.Select, label='Sprache',
                                 choices=LANGUAGES)
    code = forms.CharField(widget=forms.Textarea, label='Code')
    captcha = CaptchaField(label='CAPTCHA', only_anonymous=True)
