# -*- coding: utf-8 -*-
"""
    inyoka.utils.logger
    ~~~~~~~~~~~~~~~~~~~

    This module provides a logger.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import logging
from inyoka.conf import settings


logger = logging.getLogger('inyoka')


if not settings.DEBUG and settings.ENABLE_TRAC_LOGGING:
    from inyoka.utils.mongolog import MongoHandler
    logging_handler = MongoHandler()
    logging_handler.setLevel(logging.ERROR)
else:
    logging_handler = logging.StreamHandler()
    logging_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s:%(name)s: %(message)s'
    ))
    logging_handler.setLevel(logging.DEBUG)
logger.addHandler(logging_handler)
