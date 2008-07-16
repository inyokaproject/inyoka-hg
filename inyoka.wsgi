import site, os, sys
interpreter = '%d.%d' % sys.version_info[:2]
root = os.path.dirname(__file__)
site.addsitedir(os.path.join(root, '..', 'lib', interpreter, 'site-packages'))
os.path.append(root)

from inyoka.application import InyokaHandler
application = InyokaHandler()
