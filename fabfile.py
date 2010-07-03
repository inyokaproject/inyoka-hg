# -*- coding: utf-8 -*-
"""
    Fabfile for Inyoka
    ~~~~~~~~~~~~~~~~~~

    This script is used by fabric for easy deployment.

    :copyright: Copyright 2008 by Florian Apolloner.
    :license: GNU GPL.
"""
from fabric.api import *
import tempfile

env.user = 'ubuntu_de'
inyoka_repo = 'http://hg.ubuntu-eu.org/ubuntu-de-inyoka/'
target_dir = '~/virtualenv'

def test():
    env.hosts = ['127.0.0.1']

def staging():
    env.hosts = ['staging.ubuntuusers.de']

def production():
    env.hosts = ['dongo.ubuntu-eu.org', 'unkul.ubuntu-eu.org', 'oya.ubuntu-eu.org']

def bootstrap():
    """Create a virtual environment.  Call this once on every new server."""
    let(
        hosts = [x.strip() for x in raw_input('Servers: ').split(',')],
        python_interpreter = raw_input('Python-executable (default: python2.5): ').strip() or 'python2.5',
        target_dir = raw_input('Location (default: ~/virtualenv): ').strip().rstrip('/') or '~/virtualenv',
    )
    bootstrap = tempfile.mktemp(".py", "fabric_")
    run('mkdir %s' % target_dir)
    run('hg clone %s %s/inyoka' % (inyoka_repo, target_dir))
    local("$(python_interpreter) make-bootstrap.py > '%s'" % bootstrap)
    put(bootstrap, 'bootstrap.py')
    run('unlet PYTHONPATH; $(python_interpreter) bootstrap.py --no-site-packages %s' % target_dir)
    run("ln -s %s/inyoka/inyoka %s/lib/python`$(python_interpreter) -V 2>&1|grep -o '[0-9].[0-9]'`/site-packages" % \
            (target_dir, target_dir))

def deploy():
    """Update Inyoka and touch the wsgi file"""
    require('hosts', provided_by = [test, staging, production])
    run('cd %s/inyoka; hg pull -u %s' % (target_dir, inyoka_repo))

def easy_install():
    """Run easy_install on the server"""
    require('hosts', provided_by = [test, staging, production])
    prompt('ez', 'easy_install parameters')
    run('unlet PYTHONPATH; source %s/bin/activate; easy_install $(ez)' % target_dir)
