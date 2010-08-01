# -*- coding: utf-8 -*-
"""
    Fabfile for Inyoka
    ~~~~~~~~~~~~~~~~~~

    This script is used by fabric for easy deployment.

    :copyright: Copyright 2008 by Florian Apolloner.
    :license: GNU GPL.
"""
from fabric.api import env,run,local,put,require,prompt
from tempfile import mktemp

env.user = 'ubuntu_de'
inyoka_repo = 'ssh://hg@bitbucket.org/EnTeQuAk/inyoka-prod/'
target_dir = '~/virtualenv'

def test():
    env.hosts = ['127.0.0.1']

def staging():
    env.hosts = ['staging.ubuntuusers.de']

def production():
    env.hosts = ['dongo.ubuntu-eu.org', 'unkul.ubuntu-eu.org', 'oya.ubuntu-eu.org']

def bootstrap():
    """Create a virtual environment.  Call this once on every new server."""
    env.hosts = [x.strip() for x in raw_input('Servers: ').split(',')],
    python_interpreter = raw_input('Python-executable (default: python2.5): ').strip() or 'python2.5',
    target_dir = raw_input('Location (default: ~/virtualenv): ').strip().rstrip('/') or '~/virtualenv',
    bootstrap = mktemp(".py", "fabric_")
    run('mkdir %s' % target_dir)
    run('hg clone %s %s/inyoka' % (inyoka_repo, target_dir))
    local("%s make-bootstrap.py > '%s'" % (python_interpreter, bootstrap))
    put(bootstrap, 'bootstrap.py')
    run('unset PYTHONPATH; %s bootstrap.py --no-site-packages %s' % (python_interpreter, target_dir))
    run("ln -s %s/inyoka/inyoka %s/lib/python`%s -V 2>&1|grep -o '[0-9].[0-9]'`/site-packages" % \
            (target_dir, target_dir, python_interpreter))

def deploy():
    """Update Inyoka and touch the wsgi file"""
    require('hosts', provided_by = [test, staging, production])
    run('cd %s/inyoka; hg pull -u %s' % (target_dir, inyoka_repo))

def easy_install():
    """Run easy_install on the server"""
    require('hosts', provided_by = [test, staging, production])
    prompt('ez', 'easy_install parameters')
    run('unlet PYTHONPATH; source %s/bin/activate; easy_install $(ez)' % target_dir)

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
    local("python manage-inyoka.py mysql", capture=False)

def clean_files():
    """Clean most temporary files"""
    local("find . -name '*.pyc' -exec rm -f {} +")
    local("find . -name '*.pyo' -exec rm -f {} +")
    local("find . -name '*~' -exec rm -f {} +")
    local("find . -name '*.orig' -exec rm -f {} +")
    local("find . -name '*.orig.*' -exec rm -f {} +")
    local("find . -name '*.py.fej' -exec rm -f {} +")
