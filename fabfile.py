import tempfile

set(
    fab_user = 'ubuntu_de',
    python_interpreter = 'python',
    python_version = '2.4'
)

def test():
    set(fab_hosts = ['127.0.0.1'])

def staging():
    set(fab_hosts = ['staging.ubuntuusers.de'])

def production():
    set(fab_hosts = ['dongo.ubuntu-eu.org', 'jok.ubuntu-eu.org'])

def bootstrap():
    """Create a virtual environment.  Call this once on every new server."""
    set(fab_hosts = [x.strip() for x in raw_input('Servers: ').split(',')])
    bootstrap = tempfile.mktemp(".py", "fabric_")
    run('mkdir virtualenv')
    run('hg clone http://hg.ubuntu-eu.org/ubuntu-de-inyoka/ virtualenv/inyoka')
    local("python make-bootstrap.py > '%s'" % bootstrap)
    put(bootstrap, 'bootstrap.py')
    run('$(python_interpreter) bootstrap.py virtualenv')

def deploy():
    """Update Inyoka and touch the wsgi file"""
    require('fab_hosts', provided_by = [test, staging, production])
    run('cd virtualenv/inyoka; hg pull -u; touch inyoka.wsgi')

def easy_install():
    """Run easy_install on the server"""
    require('fab_hosts', provided_by = [test, staging, production])
    prompt('ez', 'easy_install parameters')
    run('source virtualenv/bin/activate; easy_install $(ez)')

def easy_uninstall():
    """Unstall an egg on the servers"""
    require('fab_hosts', provided_by = [test, staging, production])
    prompt('ez', 'egg to uninstall')
    run('cd virtualenv/lib/python$(python_version)/site-packages; $(python_interpreter) ~/virtualenv/inyoka/easy_uninstall.py $(ez)')
