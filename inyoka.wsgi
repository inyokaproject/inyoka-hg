if 0:
    def application(environ, start_response):
        start_response('200 OK', [('Content-Type', 'text/plain')])
        yield 'Inyoka ist wegen einer Aktualisierung kurzzeitig offline.'


import site, os, sys
interpreter = 'python%d.%d' % sys.version_info[:2]
root = os.path.dirname(__file__)
site.addsitedir(os.path.join(root, '..', 'lib', interpreter, 'site-packages'))
sys.path.append(root)

# the config
sys.path.insert(0, '/nfs/www/de')
os.environ['DJANGO_SETTINGS_MODULE'] = 'inyoka_settings'

from inyoka.application import InyokaHandler
from inyoka.wiki import parser
application = InyokaHandler()
