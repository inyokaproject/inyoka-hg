#class InyokaIsOffline(NotImplementedError):
#    pass
#raise InyokaIsOffline()

import site, os, sys
interpreter = 'python%d.%d' % sys.version_info[:2]
root = os.path.dirname(__file__)
site.addsitedir(os.path.join(root, '..', 'lib', interpreter, 'site-packages'))
sys.path.append(root)

# the config
sys.path.insert(0, '/nfs/www/de')
os.environ['DJANGO_SETTINGS_MODULE'] = 'inyoka_settings'

from inyoka.application import InyokaHandler
application = InyokaHandler()
