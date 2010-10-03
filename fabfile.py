# -*- coding: utf-8 -*-
"""
    Fabfile for Inyoka
    ~~~~~~~~~~~~~~~~~~

    This script is used by fabric for easy deployment.

    :copyright: Copyright 2008 by Florian Apolloner.
    :license: GNU GPL.
"""
import os as _os
from fabric.api import env,run,local,put,require,prompt
from tempfile import mktemp as _mktemp

env.user = 'ubuntu_de'
inyoka_repo = 'ssh://hg@bitbucket.org/EnTeQuAk/inyoka-prod-sa06/'

def test():
    """
    Fabric target for localhost
    """
    env.hosts = ['127.0.0.1']

def staging():
    """
    Fabric target for statging.ubuntuusers.de
    """
    env.hosts = ['staging.ubuntuusers.de']
    env.repository = inyoka_repo
    env.target_dir = '~/virtualenvs/inyoka-prod-sa06'

def edge():
    """
    Fabric target for edge.ubuntuusers.de
    """
    env.hosts = ['dongo.ubuntu-eu.org', 'unkul.ubuntu-eu.org', 'oya.ubuntu-eu.org']
    env.repository = inyoka_repo
    env.target_dir = '~/edge_virtualenv/inyoka'

def static():
    """
    Fabric target for static files
    """
    env.hosts = ['lisa.ubuntu-eu.org']
    env.repository = inyoka_repo
    env.target_dir = '/home/ubuntu_de_static'
    env.user = 'apollo13'

def production():
    """
    Fabric target for ubuntu-eu.org production servers
    """
    env.hosts = ['dongo.ubuntu-eu.org', 'unkul.ubuntu-eu.org', 'oya.ubuntu-eu.org']
    env.repository = inyoka_repo
    env.target_dir = '~/virtualenv/inyoka'

def bootstrap():
    """Create a virtual environment.  Call this once on every new server."""
    env.hosts = [x.strip() for x in raw_input('Servers: ').split(',')],
    python_interpreter = raw_input('Python-executable (default: python2.5): ').strip() or 'python2.5'
    target_dir = raw_input('Location (default: ~/virtualenv): ').strip().rstrip('/') or '~/virtualenv'
    bootstrap = _mktemp(".py", "fabric_")
    run('mkdir %s' % target_dir)
    run('hg clone %s %s/inyoka' % (env.repository, target_dir))
    run("%s %s/inyoka/make-bootstrap.py > %s/bootstrap.py" % (
        python_interpreter, target_dir, target_dir
    ))
    run('unset PYTHONPATH; %s %s/bootstrap.py --no-site-packages %s' % (
        python_interpreter, target_dir, target_dir
    ))
    run("ln -s %s/inyoka/inyoka %s/lib/python`%s -V 2>&1|grep -o '[0-9].[0-9]'`/site-packages" % \
            (target_dir, target_dir, python_interpreter))

def deploy():
    """Update Inyoka and touch the wsgi file"""
    require('hosts', provided_by = [test, staging, production])
    run('cd %s/inyoka; hg pull -u %s' % (env.target_dir, env.repository))

def easy_install():
    """Run easy_install on the server"""
    require('hosts', provided_by = [test, staging, production])
    prompt('ez', 'easy_install parameters')
    run('unlet PYTHONPATH; source %s/bin/activate; easy_install $(ez)' % env.target_dir)

_APPS = ['forum', 'portal', 'wiki', 'ikhaya', 'admin', 'utils', 'pastebin', 'planet']

def update_translations():
    """Recreates the pot file and updates the po files"""
    for app in _APPS:
        local('pybabel extract -F extra/babel.cfg -o inyoka/%s/locale/django.pot inyoka/%s/' % (app,app), capture=False)
        local('pybabel update -D django -i inyoka/%s/locale/django.pot -d inyoka/%s/locale -l de' % (app,app), capture=False)

def compile_translations():
    """Build gmo files from po"""
    for app in _APPS:
        local('pybabel compile -D django -d inyoka/%s/locale -l de' % app, capture=False)

def run_tests():
    """Run tests"""
    from tests import run_inyoka_suite
    run_inyoka_suite()

def reindent():
    """Reindent all python sources"""
    local("extra/reindent.py -r -B .", capture=False)

def syncdb():
    """Sync database models"""
    local("python manage-django.py syncdb", capture=False)

def migrate():
    """Migrate database"""
    local("python manage-django.py migrate", capture=False)

def create_test_data():
    """Creates some data, usefull for testing inyoka without production db dump"""
    local("python make_testdata.py", capture=False)

def convert():
    """phpBB/MoinMoin to Inyoka converter"""
    local("python inyoka/scripts/converter/converter.py", capture=False)

def server_cherrypy():
    """Start cherrypy development server"""
    local("python manage-inyoka.py runcp", capture=False)

def server():
    """Start development server"""
    local("python manage-inyoka.py runserver", capture=False)

def profiled():
    """Insert your docstring here"""
    local("python manage-inyoka.py profiled", capture=False)

def shell():
    """Start development shell"""
    local("python manage-inyoka.py shell", capture=False)

def mysql():
    """
    Start a MySQL Shell for the configured database
    """
    local("python manage-inyoka.py mysql", capture=False)

def clean_files():
    """Clean most temporary files"""
    for f in '*.py[co]', '*~', '*.orig', '*.orig.*', '*.rej':
        local("find -name '%s' -delete" % f)

def check_js():
    rhino = 'java -jar extra/js.jar'
    local("%s extra/jslint-check.js" % rhino, capture=False)


def compile_js(file=None):
    rhino = 'java -jar extra/js.jar'
    minjar = 'java -jar extra/google-compiler.jar'
    #TODO: find some way to preserve comments on top
    if file is None:
        files = _os.listdir('inyoka/static/js')
        files = [fn for fn in files if not 'min' in fn and not 'jquery-' in fn]
    else:
        files = [file]
    for file in files:
        local("%s --js inyoka/static/js/%s --warning_level QUIET > inyoka/static/js/%s" %
            (minjar, file, file.split('.js')[0] + '.min.js'), capture=False)
