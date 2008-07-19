#!/usr/bin/env python
import site, os, sys
root = os.path.dirname(__file__)
site.addsitedir(os.path.join(root, '..', 'lib', interpreter, 'site-packages'))
sys.path.append(root)

# the config
sys.path.insert(0, '/nfs/www/de')
os.environ['DJANGO_SETTINGS_MODULE'] = 'inyoka_settings'


from fastcgi import ForkingWSGIServer

import inyoka.utils.http
from inyoka.application import InyokaHandler
#from django.core.handlers.wsgi import WSGIHandler

ForkingWSGIServer(InyokaHandler(), workers=1).serve_forever()
