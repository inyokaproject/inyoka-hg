# -*- coding: utf-8 -*-
"""
    inyoka.utils.logger
    ~~~~~~~~~~~~~~~~~~~

    This module provides a logger.

    :copyright: (c) 2007-2010 by the Inyoka Team, see AUTHORS for more details.
    :license: GNU GPL, see LICENSE for more details.
"""
import logging
from logging.handlers import SMTPHandler
from inyoka.conf import settings


logger = logging.getLogger('inyoka')


if not settings.DEBUG and settings.ENABLE_TRAC_LOGGING:
    #from inyoka.utils.tracreporter import TracHandler
    #logging_handler = TracHandler()
    #logging_handler.setLevel(logging.ERROR)
#    from inyoka.utils.tracreporter import TBLoggerHandler, ErrorStackHandler
#    logging_handler = TBLoggerHandler()
#    logging_handler.setLevel(logging.ERROR)
#    logging_handler = ErrorStackHandler()
#    logging_handler.setLevel(logging.ERROR)
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
if not settings.DEBUG:
    logger.addHandler(SMTPHandler(settings.EMAIL_HOST, settings.SERVER_EMAIL,
                            [x[1] for x in settings.ADMINS],'ubuntu-de ERROR'))
