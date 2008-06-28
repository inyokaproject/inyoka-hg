#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Source line counter
    ~~~~~~~~~~~~~~~~~~~

    Count the lines of inyoka.

    :copyright: 2006-2007 by Armin Ronacher, 2008 by Christopher Grebs.
    :license: GNU GPL, see LICENSE for more details.
"""
import os
from os import path


def main(root, search):
    LOC = 0

    root = path.abspath(root)

    print '+%s+' % ('=' * 78)
    print '| Lines of Code %s |' % (' ' * 62)
    print '+%s+' % ('=' * 78)

    for folder in search:
        off = 78/2 - len(folder)
        print '+%s  %s  %s+' % ('-' * off, folder, '-' * (off +1))
        folder = path.join(root, folder)
        for base, dirname, files in os.walk(folder):
            for fn in files:
                if fn.endswith('.py') or fn.endswith('.js') or fn.endswith('.html'):
                    try:
                        fp = file(path.join(base, fn))
                        lines = sum(1 for l in fp.read().splitlines() if l.strip())
                    except:
                        print '%-70sskipped' % fn
                    else:
                        LOC += lines
                        print '| %-68s %7d |' % (fn, lines)
                    fp.close()

    print '+%s+' % ('-' * 78)
    print '| Total Lines of Code: %55d |' % LOC
    print '+%s+' % ('-' * 78)

if __name__ == '__main__':
    main('.', ['inyoka', 'extra', 'tests'])
