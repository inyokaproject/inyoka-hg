# -*- coding: utf-8 -*-
"""
    inyoka.utils.logger
    ~~~~~~~~~~~~~~~~~~~

    This module provides a logger.

    :copyright: Copyright 2008 by Armin Ronacher.
    :license: GNU GPL.
"""
import logging
from django.conf import settings


logger = logging.getLogger('inyoka')


if settings.DEBUG:
    from inyoka.utils.tracreporter import TracHandler
    logging_handler = TracHandler()
    logging_handler.setLevel(logging.ERROR)
else:
    logging_handler = logging.StreamHandler()
    logging_handler.setFormatter(Formatter(
        '[%(asctime)s] %(levelname)s:%(name)s: %(message)s'
    ))
    logging_handler.setLevel(logging.DEBUG)
logger.setHandler(logging_handler)
