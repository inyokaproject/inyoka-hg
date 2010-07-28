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
import os
import random
import posixpath
import unicodedata
from inyoka.conf import settings


_str_num_re = re.compile(r'(?:[^\d]*(\d+)[^\d]*)+')
_path_crop = re.compile(r'^(\.\.?/)+')
_unsupported_re = re.compile(r'[\x00-\x19#%?]+')
_slugify_replacement_table = {
    u'\xdf': 'ss',
    u'\xe4': 'ae',
    u'\xe6': 'ae',
    u'\xf0': 'dh',
    u'\xf6': 'oe',
    u'\xfc': 'ue',
    u'\xfe': 'th',
}
_slugify_word_re = re.compile(ur'[^a-zA-Z0-9%s]+' %
    u''.join(re.escape(c) for c in _slugify_replacement_table.keys()))


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
    if isinstance(string, str):
        string = string.decode(settings.DEFAULT_CHARSET)
    result = []
    if convert_lowercase:
        string = string.lower()
    for word in _slugify_word_re.split(string.strip()):
        if word:
            for search, replace in _slugify_replacement_table.iteritems():
                word = word.replace(search, replace)
            word = unicodedata.normalize('NFKD', word)
            result.append(word.encode('ascii', 'ignore'))
    return u'-'.join(result)


def human_number(number, genus=None):
    """Numbers from 1 - 12 are words."""
    if not 0 < number <= 12:
        return str(number)
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

def shorten_filename(name, length=20, suffix=''):
    """
    Shorten the `name` to the specified `length`.
    If `suffix` is given append it before the extension.

    >>> shorten_filename("FoobarBaz.tar.gz", 15, "-2")
    'Foobar-2.tar.gz'
    >>> shorten_filename("Foobar.tar.gz", 9, "-1")
    Traceback (most recent call last):
      ...
    ValueError: -1.tar.gz is >= 9 chars
    """
    try:
        name, extension = name.split('.', 1)
        dot = '.'
    except ValueError:
        extension = dot = ''
    new_suffix = suffix + dot + extension
    slice_index = length - len(new_suffix)
    if slice_index <= 0:
        raise ValueError, "%s is >= %d chars" % (new_suffix, length)
    return name[:length - len(new_suffix)] + new_suffix

def get_new_unique_filename(name, path='', shorten=True, length=20):
    counter = 0
    new_name = shorten_filename(name, length)
    while os.path.exists(os.path.join(path, new_name)):
        counter += 1
        new_name = shorten_filename(name, length, suffix="-" + str(counter))
    return new_name


# Old Version, maybe gets reactivated once testing with new method (see below)
# does not get better excerpts
#
#def create_excerpt(text, terms, length=350):
#    """
#    """
#    # find the first occurence of a term in the text
#    idx = 0
#    first_term = ''
#    for term in terms:
#        try:
#            i = text.index(term)
#        except ValueError:
#            i = 0
#        if i > idx or not idx:
#            idx = i
#            first_term = term
#
#    # find the best position to start the excerpt
#    if idx + len(first_term) < length:
#        excerpt = text[:length]
#        if len(excerpt) < len(text):
#            excerpt += u'...'
#    else:
#        excerpt = u'...%s' % text[idx:idx + length]
#        if len(text) > idx + length:
#            excerpt += u'...'
#    excerpt = escape(excerpt)
#
#
#    # highlight the terms in the excerpt
#    r = re.compile('(%s)' % '|'.join(terms))
#    excerpt = ''.join(i % 2 != 0 and '<strong>%s</strong>' % part or part
#                      for i, part in enumerate(r.split(excerpt)))
#    return excerpt



def find_highlightable_terms(text, terms):
    # Use a set so we only do this once per unique term.
    positions = {}

    # Pre-compute the length.
    end_offset = len(text)
    lower_text_block = text.lower()

    for term in terms:
        if not term in positions:
            positions[term] = []

        start_offset = 0

        while start_offset < end_offset:
            next_offset = lower_text_block.find(term, start_offset, end_offset)

            # If we get a -1 out of find, it wasn't found. Bomb out and
            # start the next term.
            if next_offset == -1:
                break

            positions[term].append(next_offset)
            start_offset = next_offset + len(term)

    return positions


def find_window(highlight_locations, max_length):
    best_start = 0
    best_end = max_length

    # First, make sure we have terms.
    if not len(highlight_locations):
        return (best_start, best_end)

    terms_found = []

    # Next, make sure we found any terms at all.
    for term, offset_list in highlight_locations.items():
        if len(offset_list):
            # Add all of the locations to the list.
            terms_found.extend(offset_list)

    if not len(terms_found):
        return (best_start, best_end)

    if len(terms_found) == 1:
        return (terms_found[0], terms_found[0] + max_length)

    # Sort the list so it's in ascending order.
    terms_found = sorted(terms_found)

    # We now have a denormalized list of all positions were a term was
    # found. We'll iterate through and find the densest window we can by
    # counting the number of found offsets (-1 to fit in the window).
    highest_density = 0

    if terms_found[:-1][0] > max_length:
        best_start = terms_found[:-1][0]
        best_end = best_start + max_length

    for count, start in enumerate(terms_found[:-1]):
        current_density = 1

        for end in terms_found[count + 1:]:
            if end - start < max_length:
                current_density += 1
            else:
                current_density = 0

            # Only replace if we have a bigger (not equal density) so we
            # give deference to windows earlier in the document.
            if current_density > highest_density:
                best_start = start
                best_end = start + max_length
                highest_density = current_density

    return (best_start, best_end)


def render_html(text_block, highlight_locations=None, start_offset=None, end_offset=None):
    # Start by chopping the block down to the proper window.
    text = text_block[start_offset:end_offset]

    # Invert highlight_locations to a location -> term list
    term_list = []

    for term, locations in highlight_locations.items():
        term_list += [(loc - start_offset, term) for loc in locations]

    loc_to_term = sorted(term_list)

    hl_start, hl_end = (' <strong>', '</strong> ')
    highlight_length = len(hl_start + hl_end)

    # Copy the part from the start of the string to the first match,
    # and there replace the match with a highlighted version.
    highlighted_chunk = ""
    matched_so_far = 0
    prev = 0
    prev_str = ""

    for cur, cur_str in loc_to_term:
        # This can be in a different case than cur_str
        actual_term = text[cur:cur + len(cur_str)]

        # Handle incorrect highlight_locations by first checking for the term
        if actual_term.lower() == cur_str:
            highlighted_chunk += text[prev + len(prev_str):cur] + hl_start + actual_term + hl_end
            prev = cur
            prev_str = cur_str

            # Keep track of how far we've copied so far, for the last step
            matched_so_far = cur + len(actual_term)

    # Don't forget the chunk after the last term
    highlighted_chunk += text[matched_so_far:]

    if start_offset > 0:
        highlighted_chunk = '...%s' % highlighted_chunk

    if end_offset < len(text_block):
        highlighted_chunk = '%s...' % highlighted_chunk

    return highlighted_chunk


def create_excerpt(text, terms, length=350):
    text = striptags(text)
    highlight_locations = find_highlightable_terms(text, terms)
    start_offset, end_offset = find_window(highlight_locations, length * 2)
    return render_html(escape(text), highlight_locations, start_offset, end_offset)


# circular imports
from inyoka.utils.html import escape, striptags
