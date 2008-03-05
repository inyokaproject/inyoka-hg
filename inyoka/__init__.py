# -*- coding: utf-8 -*-
"""
    inyoka
    ~~~~~~

    The inyoka portal system.  The system is devided into multiple modules
    to which we refer as applications.  The name inyoka means "snake" in
    zulu and was chosen because it's a python application *cough*.

    Although the software is based on django we use different idoms and a
    non standard template engine called Jinja.  The basic application
    structure is explained below.


    Requirements
    ============

    The code is only tested with MySQL (we use a couple of custom SQL queries)
    but might work with Postgres too if we find a subset.  The option is left
    open so that we can eventually switch to Postgres if there are good reasons
    for it.

    Additionally Jinja 1.2 or higher is required as well as xapian for the
    full text search facilities.  For the planet application the feedparser
    library must be installed.  Additionally chardet is recommended so that
    it can better guess broken encodings of feeds.  For the pastebin, wiki and
    some other parts `pygments` 0.8 or higher must be available.
    MySQL must support InnoDB or any other transaction engine like falcon
    (untested though).  For incoming HTML data that is converted to XHTML
    we also need html5lib.
    To let the inyoka services run (required) you need also simplejson.

    The most recent django version is required, we keep it in sync with the
    django sources weekly.

    For deployment memcached is the preferred caching system.  Otherwise use
    many threads and few processes and enable `locmem`.


    Configuration
    =============

    The default configuration the development, test and production
    configuration files should start import is in `inyoka.default_settings`.
    This file is not referenced by the application code itself which means
    that you can import it as part of the django setup without causing
    circular bootstrapping dependencies.


    Quickstart
    ==========

    To get inyoka running you have to install the dependencies and then create
    a ``development_settings.py`` in the root folder, next to the example
    settings file.  It could look like that::

        from example_development_settings import *

        DATABASE_NAME = 'inyoka'
        DATABASE_USER = 'root'
        XAPIAN_DATABASE = '/home/user/dev/inyoka/inyoka.xapdb'

    After that all you have to do before working with inyoka is sourcing the
    `init.sh` file (``source init.sh`` or ``. init.sh``).

    Then you can use the Makefile which provides comments for resetting the
    database, starting the server, building the documentation etc.  For more
    details have a look at the Makefile.


    Contents
    ========

    The following applications are part of inyoka so far:

    `portal`
        The index application.  On no subdomain and the portal page.
        Aggregates recent ikhaya posts and similar stuff.  Also shows the
        number of online users.

    `forum`
        The forum component.  It's inspired by phpBB2 which was previously
        used on the German ubuntuusers.de webpage.  Some of the functionallity
        was extended over time though.  Especially an improved notification
        system, attachments and subforums (latter new in inyoka)

    `wiki`
        Moin inspired wiki engine.  It's not yet as advanced as moin 1.7 but
        has revisioned pages a better parser which can savely generate docbook
        and other XML based output formats.  The wiki parser also has some
        BBCode elements for compatibility with the old phpBB syntax and is
        used in other components (`forum`, `ikhaya`, ...) as well.

    `planet`
        A planet planet like feed aggregator.  It has archives and santized
        input data thanks to feedparser.

    `ikhaya`
        Ikhaya is zulu for `home` and a blog application.  It's used on the
        German ubuntuusers portal for site wide annoucements and other news.
        It doesn't show up on the planet automatically, for that you have to
        add the ikhaya feed to it like for any other blog too.

    `pastebin`
        A pastebin that uses Pygments for highlighting.  It does not support
        diffing yet but allows to download pastes.


    :copyright: Copyright 2007-2008 by Armin Ronacher, Christian Hack,
                Benjamin Wiegand, Maximilian Trescher.
    :license: GNU GPL.
"""


def _bootstrap():
    """Get the inyoka version and setup fake modules"""
    global INYOKA_REVISION
    import os, inyoka, new, sys
    from subprocess import Popen, PIPE

    # boostrap fake modules
    sys.modules['inyoka.static'] = static = new.module('inyoka.static')
    sys.modules['inyoka.media'] = media = new.module('inyoka.media')

    # get inyoka revision
    hg = Popen(['hg', 'tip'], stdout=PIPE, stderr=PIPE, stdin=PIPE,
               cwd=os.path.dirname(inyoka.__file__))
    hg.stdin.close()
    hg.stderr.close()
    rv = hg.stdout.read()
    hg.stdout.close()
    hg.wait()
    hg_node = None
    if hg.wait() == 0:
        for line in rv.splitlines():
            p = line.split(':', 1)
            if len(p) == 2 and p[0].lower().strip() == 'changeset':
                hg_node = p[1].strip().split(':')[0]
                break
    INYOKA_REVISION = hg_node

_bootstrap()
del _bootstrap
