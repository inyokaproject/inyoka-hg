from inyoka.default_settings import *
from os.path import join

DATABASE_NAME = 'ubuntuusers'
DATABASE_USER = 'root'

# debug settings
DEBUG = ENABLE_DEBUGGER = True
ENABLE_TRAC_LOGGING = False

# url settings
BASE_DOMAIN_NAME = 'ubuntuusers.local:8080'
SESSION_COOKIE_DOMAIN = '.ubuntuusers.local'
MEDIA_URL = 'http://media.%s' % BASE_DOMAIN_NAME
STATIC_URL = 'http://static.%s' % BASE_DOMAIN_NAME
ADMIN_MEDIA_PREFIX = STATIC_URL + '/_admin/'
INYOKA_SYSTEM_USER_EMAIL = 'system@' + BASE_DOMAIN_NAME
GOOGLE_MAPS_APIKEY = 'ABQIAAAAnGRs_sYisCDW3FXIZAzZ9RR0WYmUN-JWdjE121Rerp-F3KIi4BQQM-N93TqupJwysf0dHBu_LfF6AQ'
TRAC_URL = 'http://trac.staging.ubuntuusers.de'
TRAC_USER = 'logger'
TRAC_PASSWORD = None
