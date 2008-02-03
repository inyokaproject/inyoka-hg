# -*- coding: utf-8 -*-
"""
    test_wiki_utils
    ~~~~~~~~~~~~~~~

    Test the wiki utilities.

    :copyright: Copyright 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from inyoka.wiki.utils import pagename_join, normalize_pagename


def test_pagename_join():
    j = pagename_join
    assert j("Foo", "Bar") == "Foo/Bar"
    assert j("Foo", "Bar/Baz") == "Bar/Baz"
    assert j("Foo", "./Bar/Baz") == "Foo/Bar/Baz"
    assert j("Foo", "./Bar") == "Foo/Bar"
    assert j("Foo/Bar", "../Blah") == "Foo/Blah"
    assert j("Foo/Bar", "./Blah") == "Foo/Bar/Blah"
    assert j("Foo", "../../../Blub") == "Blub"


def test_normalize_pagename():
    n = normalize_pagename
    assert n("Foo Bar") == "Foo_Bar"
    assert n("/Foo_Bar/") == "Foo_Bar"
    assert n("Foo%Bar?#") == "FooBar"
