#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Inyoka Bootstrap Creation Script
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Creates a bootstrap script for inyoka.

    :copyright: Copyright 2008 by Florian Apolloner.
    :license: GNU GPL.
"""

import os, subprocess

import virtualenv

EXTRA_TEXT = """
def easy_install(package, home_dir, optional_args=None):
    optional_args = optional_args or []
    cmd = [os.path.join(home_dir, 'bin', 'easy_install')]
    cmd.extend(optional_args)
    cmd.append(package)
    call_subprocess(cmd)

def after_install(options, home_dir):
    input = 'x'
    while not input.lower() in 'yn':
        input = raw_input('Install the neccessary header files via apt-get (y/n): ')
    if input.lower() == 'y':
        call_subprocess(['sudo', 'apt-get', 'install', 'libmemcache-dev', 'libxapian-dev', 'python-dev', 'swig'])
        call_subprocess(['sudo', 'apt-get', 'build-dep', 'python-mysqldb', 'python-imaging'])
    else:
        print 'Not installing developement headers.'
    easy_install('Jinja2', home_dir) 
    easy_install('Werkzeug', home_dir)
    easy_install('Pygments', home_dir)
    easy_install('SQLAlchemy==0.4.6', home_dir)
#    easy_install('Imaging', home_dir, ['--find-links', 'http://www.pythonware.com/products/pil/']) # wtf is wrong with it?
    easy_install('simplejson', home_dir)
    easy_install('pytz', home_dir)
    easy_install('html5lib', home_dir)
    easy_install('dnspython', home_dir)
    easy_install('wsgiref', home_dir)
    easy_install('MySQL-python', home_dir) # Install via apt-get
    easy_install('http://feedparser.googlecode.com/files/feedparser-4.1.zip', home_dir)
    easy_install('http://code.djangoproject.com/svn/django/trunk/', home_dir)
    easy_install('http://gijsbert.org/downloads/cmemcache/cmemcache-0.95.tar.bz2', home_dir)

"""

def main():
    print virtualenv.create_bootstrap_script(EXTRA_TEXT, python_version='2.4')

if __name__ == '__main__':
    main()
