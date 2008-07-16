#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    Easy_fucking_uninstall ;)
    ~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import glob, sys, os, shutil

eggs = glob.glob('%s*' % sys.argv[1])
for egg in eggs:
    if egg.endswith('.egg-link'):
        data = file(egg,'r').readlines()[0]
    else:
        data = './%s' % egg
    file('easy-install.pth', 'w').write(file('easy-install.pth', 'r').read().replace('%s\n' % data, ''))
    try:
        os.remove(egg)
        shutil.rmtree(egg, True)
    except OSError:
        pass
