set(
    fab_user = 'ubuntu_de',
    inyoka_user = 'ubuntu_de',
    inyoka_password = 'xxx'
)

def test():
    set(fab_hosts = ['127.0.0.1'])

def staging():
    set(fab_hosts = ['staging.ubuntuusers.de'])

def production():
    set(fab_hosts = ['x.ubuntu-eu.org', 'y.ubuntu-eu.org'],)

def upload_wsgifile():
    """Uploads a wsgifile"""
    require('fab_hosts', provided_by = [test, staging, production])
    put('welches files?!', 'inyoka.wsgi')

def checkout_inyoka():
    """Create a inyoka clone"""
    require('fab_hosts', provided_by = [test, staging, production])
    run('hg clone http://$(inyoka_user):$(inyoka_password)@hg.ubuntu-eu.org/ubuntu-de-inyoka/ inyoka')

def create_virtualenv():
    """Set up the virtualenv on each host"""
    require('fab_hosts', provided_by = [test, staging, production])
    local('python make-bootstrap.py > bootstrap.py')
    put('bootstrap.py', 'bootstrap.py')
    run('python2.4 bootstrap.py virtualenv')

def deploy():
    """Update Inyoka and touch the wsgi file"""
    require('fab_hosts', provided_by = [test, staging, production])
    run('hg pull -u /home/ubuntu_de/inyoka')
    run('touch /home/ubuntu_de/inyoka.wsgi')

def all():
    upload_wsgifile()
    checkout_inyoka()
    create_virtualenv()
    deploy()
