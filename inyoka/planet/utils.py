# -*- coding: utf-8 -*-
"""
    inyoka.planet.utils
    ~~~~~~~~~~~~~~~~~~~

    Various utilities for the planet.


    :copyright: 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from datetime import date


def group_by_day(entries):
    """Group some entries by day."""
    days = []
    days_found = set()
    for entry in entries:
        key = (entry.pub_date.year, entry.pub_date.month, entry.pub_date.day)
        if key not in days_found:
            days.append((key, []))
            days_found.add(key)
        days[-1][1].append(entry)

    return [{
        'date':     date(*key),
        'articles': entries
    } for key, entries in days if entries]
