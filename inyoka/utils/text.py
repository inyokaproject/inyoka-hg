# -*- coding: utf-8 -*-
"""
    inyoka.utils.text
    ~~~~~~~~~~~~~~~~~

    Various text realated tools.

    :copyright: Copyright 2007-2008 by Armin Ronacher, Benjamin Wiegand,
                Christopher Grebs.
    :license: GNU GPL.
"""
import re
import random
import posixpath
import unicodedata


_str_num_re = re.compile(r'(?:[^\d]*(\d+)[^\d]*)+')
_path_crop = re.compile(r'^(..?/)+')
_unsupported_re = re.compile(r'[\x00-\x19#%?]+')
_punctuation_re = re.compile(r'[\s!"#$%&\'()*\-/<=>?@\[\\\]^_`{|},;]+')
_slugify_replacement_table = {
    u'\xdf': 'ss',
    u'\xe4': 'ae',
    u'\xe6': 'ae',
    u'\xf0': 'dh',
    u'\xf6': 'oe',
    u'\xfc': 'ue',
    u'\xfe': 'th'
}



def increment_string(s):
    """Increment a number in a string or add a number."""
    m = _str_num_re.search(s)
    if m:
        next = str(int(m.group(1))+1)
        start, end = m.span(1)
        return s[:max(end - len(next), start)] + next + s[end:]
    return s + '2'


def get_random_password():
    """This function returns a pronounceable word."""
    consonants = 'bcdfghjklmnprstvwz'
    vowels = 'aeiou'
    numbers = '0123456789'
    all = consonants + vowels + numbers
    length = random.randrange(8, 12)
    password = u''.join(
        random.choice(consonants) +
        random.choice(vowels) +
        random.choice(all) for x in xrange(length // 3)
    )[:length]
    return password


def slugify(string, convert_lowercase=True):
    """Slugify a string."""
    result = []
    if convert_lowercase:
        string = string.lower()
    for word in _punctuation_re.split(string.strip()):
        if word:
            for search, replace in _slugify_replacement_table.iteritems():
                word = word.replace(search, replace)
            word = unicodedata.normalize('NFKD', word)
            result.append(word.encode('ascii', 'ignore'))
    return u'-'.join(result)


def human_number(number, genus=None):
    """Numbers from 1 - 12 are words."""
    if not 0 < number <= 12:
        return number
    if number == 1:
        return {
            'masculine':    'ein',
            'feminine':     'eine',
            'neuter':       'ein'
        }.get(genus, 'eins')
    return ('zwei', 'drei', 'vier', u'fünf', 'sechs',
            'sieben', 'acht', 'neun', 'zehn', 'elf', u'zwölf')[number - 2]


def join_pagename(name1, name2):
    """
    Join a page with another one.  This works similar to a normal filesystem
    path join but with different rules.  Here some examples:

    >>> pagename_join('Foo', 'Bar')
    'Foo/Bar'
    >>> pagename_join('Foo', '/Bar')
    'Bar'
    >>> pagename_join('Foo', 'Bar/Baz')
    'Bar/Baz'
    >>> pagename_join('Foo', './Bar/Baz')
    'Foo/Bar/Baz'
    """
    if not isinstance(name1, basestring):
        name1 = name1.name
    if not isinstance(name2, basestring):
        name2 = name2.name
    if '/' in name2 and not _path_crop.match(name2):
        name2 = '/' + name2
    path = posixpath.join(name1, name2).lstrip('/')
    return _path_crop.sub('', posixpath.normpath(path))


def normalize_pagename(name, strip_location_markers=True):
    """
    Normalize a pagename.  Strip unsupported characters.  You have to call
    this function whenever you get a pagename from user input.  The models
    itself never check for normalized names and passing unnormalized page
    names to the models can cause serious breakage.

    If the second parameter is set to `False` the leading slashes or slash
    like path location markers are not removed.  That way the pagename is
    left unnormalized to a part but will be fully normalized after a
    `pagename_join` call.
    """
    name = u'_'.join(_unsupported_re.sub('', name).split()).rstrip('/')
    if not strip_location_markers:
        return name
    if name.startswith('./'):
        return name[2:]
    elif name.startswith('../'):
        return name[3:]
    return name.lstrip('/')


def get_pagetitle(name, full=True):
    """
    Get the title for a page by name.  Per default it just returns the title
    for the full page, not just the last part.  If you just want the part
    after the last slash set `full` to `False`.
    """
    name = normalize_pagename(name)
    if not full:
        name = name.rsplit('/', 1)[-1]
    return u' '.join(x for x in name.split('_') if x)


def shorten_filename(name, length=20):
    """
    Shorten the `name` to the specified `length`.
    """
    try:
        name, extension = name.rsplit('.', 1)
        return name[:length - len(extension) - 1] + '.' + extension
    except ValueError:
        extension = ''
        return name[:length]


def create_excerpt(text, terms, length=350):
    """
    """
    # find the first occurence of a term in the text
    idx = 0
    first_term = ''
    for term in terms:
        try:
            i = text.index(term)
        except ValueError:
            i = 0
        if i > idx or not idx:
            idx = i
            first_term = term

    # find the best position to start the excerpt
    if idx + len(first_term) < length:
        excerpt = text[:length]
        if len(excerpt) < len(text):
            excerpt += u'...'
    else:
        excerpt = u'...%s' % text[idx:idx + length]
        if len(text) > idx + length:
            excerpt += u'...'
    excerpt = escape(excerpt)


    # highlight the terms in the excerpt
    r = re.compile('(%s)' % '|'.join(terms))
    excerpt = ''.join(i % 2 != 0 and '<strong>%s</strong>' % part or part
                      for i, part in enumerate(r.split(excerpt)))
    return excerpt


# circular imports
from inyoka.utils.html import escape
