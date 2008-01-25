#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    inyoka.scripts.clean_thumbnail_cache
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This script removes unused thumbnails from the wiki thumbnail cache.

    :copyright: 2007 by Arimin Ronacher.
    :license: GNU GPL.
"""
from inyoka.wiki.utils import clean_thumbnail_cache as clean_wiki_cache


def main():
    print 'Cleaning wiki thumbnail cache...',
    print '%d files deleted' % len(clean_wiki_cache())


if __name__ == '__main__':
    main()
