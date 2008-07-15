import tempfile

set(
    fab_user = 'ubuntu_de',
    python_interpreter = 'python'
)

def test():
    set(fab_hosts = ['127.0.0.1'])

def staging():
    set(fab_hosts = ['staging.ubuntuusers.de'])

def production():
    set(fab_hosts = ['yurugu.ubuntu-eu.org'])

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
    run('cd virtualenv/inyoka; hg pull -u')
    run('cd ..; touch inyoka.wsgi')
