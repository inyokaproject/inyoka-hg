#!/usr/bin/env python
import os
from django.core.management import execute_manager
from django.utils.importlib import import_module

mod = import_module(os.environ['DJANGO_SETTINGS_MODULE'])

from inyoka.application import *
from inyoka.conf import settings


try:
    import south
    settings.INSTALLED_APPS += ('south',)
    del south
except ImportError:
    pass


if __name__ == "__main__":
    execute_manager(mod)
