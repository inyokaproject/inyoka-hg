# -*- coding: utf-8 -*-
"""
    inyoka.utils.diff3
    ~~~~~~~~~~~~~~~~~~

    A diff3 algorithm implementation.  Lousely based on the version of the
    MoinMoin wiki engine.


    :copyright: Copyright 2007 by Armin Ronacher, Florian Festi.
    :license: GNU GPL.
"""


DEFAULT_MARKERS = (
    '<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<',
    '========================================',
    '>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>'
)


class DiffConflict(ValueError):
    """
    Raised if a conflict occoured and the merging operated in non
    conflict mode.
    """

    def __init__(self, old_lineno, other_lineno, new_lineno):
        ValueError.__init__(self, 'conflict on line %d' % other_lineno)
        self.old_lineno = old_lineno
        self.other_lineno = other_lineno
        self.new_lineno = new_lineno


def merge(old, other, new, allow_conflicts=True, markers=None):
    """
    Works like `stream_merge` but returns a string.
    """
    return '\n'.join(stream_merge(old, other, new, allow_conflicts, markers))


def stream_merge(old, other, new, allow_conflicts=True, markers=None):
    """
    Merges three strings or lists of lines.  The return values is an iterator.
    Per default conflict markers are added to the source, you can however set
    :param allow_conflicts: to `False` which will get you a `DiffConflict`
    exception on the first encountered conflict.
    """
    if isinstance(old, basestring):
        old = old.splitlines()
    elif not isinstance(old, list):
        old = list(old)
    if isinstance(other, basestring):
        other = other.splitlines()
    elif not isinstance(other, list):
        other = list(other)
    if isinstance(new, basestring):
        new = new.splitlines()
    elif not isinstance(new, list):
        new = list(new)
    left_marker, middle_marker, right_marker = markers or DEFAULT_MARKERS

    old_lineno = other_lineno = new_lineno = 0
    old_len = len(old)
    other_len = len(other)
    new_len = len(new)

    while old_lineno < old_len and \
          other_lineno < other_len and \
          new_lineno < new_len:

        # unchanged
        if old[old_lineno] == other[other_lineno] == new[new_lineno]:
            yield old[old_lineno]
            old_lineno += 1
            other_lineno += 1
            new_lineno += 1
            continue

        new_match = find_match(old, new, old_lineno, new_lineno)
        other_match = find_match(old, other, old_lineno, other_lineno)

        # new is changed
        if new_match != (old_lineno, new_lineno):
            new_changed_lines = new_match[0] - old_lineno

            # other is unchanged
            if match(old, other, old_lineno, other_lineno,
                     new_changed_lines) == new_changed_lines:
                for item in new[new_lineno:new_match[1]]:
                    yield item
                old_lineno = new_match[0]
                new_lineno = new_match[1]
                other_lineno += new_changed_lines

            # both changed, conflict!
            else:
                if not allow_conflicts:
                    raise DiffConflict(old_lineno, other_lineno, new_lineno)
                old_m, other_m, new_m = tripple_match(old, other, new,
                                                      other_match, new_match)
                yield left_marker
                for item in other[other_lineno:other_m]:
                    yield item
                yield middle_marker
                for item in new[new_lineno:new_m]:
                    yield item
                yield right_marker
                old_lineno = old_m
                other_lineno = other_m
                new_lineno = new_m

        # other is changed
        else:
            other_changed_lines = other_match[0] - other_lineno

            # new is unchanged
            if match(old, new, old_lineno, new_lineno,
                     other_changed_lines) == other_changed_lines:
                for item in other[other_lineno:other_match[1]]:
                    yield item
                old_lineno = other_match[0]
                other_lineno = other_match[1]
                new_lineno += other_changed_lines

            # both changed, conflict!
            else:
                if not allow_conflicts:
                    raise DiffConflict(old_lineno, other_lineno, new_lineno)

                old_m, other_m, new_m = tripple_match(old, other, new,
                                                      other_match, new_match)
                yield left_marker
                for item in other[other_lineno:other_m]:
                    yield item
                yield middle_marker
                for item in new[new_lineno:new_m]:
                    yield item
                yield right_marker
                old_lineno = old_m
                other_lineno = other_m
                new_lineno = new_m

    # all finished
    if (old_lineno == old_len and other_lineno == other_len
        and new_lineno == new_len):
        return

    # new added lines
    if old_lineno == old_len and other_lineno == other_len:
        for item in new[new_lineno:]:
            yield item

    # other added lines
    elif old_lineno == old_len and new_lineno == new_len:
        for item in other[other_lineno:]:
            yield item

    # conflict
    elif not (
        (new_lineno == new_len and
         (old_len - old_lineno == other_len - other_lineno) and
         match(old, other, old_lineno, other_lineno, old_len - old_lineno)
         == old_len - old_lineno) and
        (other_lineno == other_len and
         (old_len - old_lineno == new_len-new_lineno) and
         match(old, new, old_lineno, new_lineno, old_len - old_lineno)
         == old_len - old_lineno)):
        if new == other:
            for item in new[new_lineno:]:
                yield item
        else:
            if not allow_conflicts:
                raise DiffConflict(old_lineno, other_lineno, new_lineno)
            yield left_marker
            for item in other[other_lineno:]:
                yield item
            yield middle_marker
            for item in new[new_lineno:]:
                yield item
            yield right_marker


def tripple_match(old, other, new, other_match, new_match):
    """
    Find next matching pattern unchanged in both other and new return the
    position in all three lists.  Unlike `merge` this only operates on
    lists.
    """
    while 1:
        difference = new_match[0] - other_match[0]

        # new changed more lines
        if difference > 0:
            match_len = match(old, other, other_match[0], other_match[1],
                              difference)
            if match_len == difference:
                return new_match[0], other_match[1] + difference, new_match[1]
            other_match = find_match(old, other,
                                     other_match[0] + match_len,
                                     other_match[1] + match_len)

        # other changed more lines
        elif difference < 0:
            difference = -difference
            match_len = match(old, new, new_match[0], new_match[1],
                              difference)
            if match_len == difference:
                return (other_match[0], other_match[1],
                        new_match[0] + difference)
            new_match = find_match(old, new,
                                   new_match[0] + match_len,
                                   new_match[1] + match_len)

        # both conflicts change same number of lines
        # or no match till the end
        else:
            return new_match[0], other_match[1], new_match[1]


def match(list1, list2, nr1, nr2, maxcount=3):
    """
    Return the number matching items after the given positions maximum
    maxcount lines are are processed.  Unlike `merge` this only operates
    on lists.
    """
    i = 0
    len1 = len(list1)
    len2 = len(list2)
    while nr1 < len1 and nr2 < len2 and list1[nr1] == list2[nr2]:
        nr1 += 1
        nr2 += 1
        i += 1
        if i >= maxcount and maxcount > 0:
            break
    return i


def find_match(list1, list2, nr1, nr2, mincount=3):
    """
    searches next matching pattern with lenght mincount
    if no pattern is found len of the both lists is returned
    """
    idx1 = nr1
    idx2 = nr2
    len1 = len(list1)
    len2 = len(list2)
    hit1 = hit2 = None

    while idx1 < len1 or idx2 < len2:
        i = nr1
        while i <= idx1:
            hit_count = match(list1, list2, i, idx2, mincount)
            if hit_count >= mincount:
                hit1 = (i, idx2)
                break
            i += 1

        i = nr2
        while i < idx2:
            hit_count = match(list1, list2, idx1, i, mincount)
            if hit_count >= mincount:
                hit2 = (idx1, i)
                break
            i += 1

        if hit1 or hit2:
            break
        if idx1 < len1:
            idx1 += 1
        if idx2 < len2:
            idx2 += 1

    if hit1 and hit2:
        return hit1
    elif hit1:
        return hit1
    elif hit2:
        return hit2
    return len1, len2
