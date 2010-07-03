#!/usr/bin/env python
import os
from django.core.management import execute_manager
from django.utils.importlib import import_module

mod = import_module(os.environ['DJANGO_SETTINGS_MODULE'])

from inyoka import application

if __name__ == "__main__":
    execute_manager(mod)
