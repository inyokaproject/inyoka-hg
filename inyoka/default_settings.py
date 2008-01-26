# -*- coding: utf-8 -*-
"""
    inyoka.default_settings
    ~~~~~~~~~~~~~~~~~~~~~~~

    The inyoka default settings.

    :copyright: 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
from os.path import dirname, join

# the base path of the application
BASE_PATH = dirname(__file__)

# debugger is off per default
DEBUG = TEMPLATE_DEBUG = False

# per default there are no managers and admins
MANAGERS = ADMINS = ()

# set the database settings in the actual settings file
DATABASE_NAME = DATABASE_USER = DATABASE_HOST = DATABASE_PORT = ''

# mysql only
DATABASE_ENGINE = 'mysql'
DATABASE_OPTIONS = {
    'init_command': "set storage_engine=INNODB"
}


# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be avilable on all operating systems.
TIME_ZONE = 'Europe/Vienna'

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
LANGUAGE_CODE = 'de-de'
DATETIME_FORMAT = 'j. F Y H:i'
DATE_FORMAT = 'j. F Y'
TIME_FORMAT = 'H:i'

# leave that unchanged, it's unused right now
SITE_ID = 1

# the base url (without subdomain)
BASE_DOMAIN_NAME = 'ubuntuusers.de'
SESSION_COOKIE_DOMAIN = '.%s' % BASE_DOMAIN_NAME.split(':')[0]

# The URL confs for the subdomains
SUBDOMAIN_MAP = {
    '':         'inyoka.portal.urls',
    'planet':   'inyoka.planet.urls',
    'ikhaya':   'inyoka.ikhaya.urls',
    'wiki':     'inyoka.wiki.urls',
    'paste':    'inyoka.pastebin.urls',
    'static':   'inyoka.static.urls',
    'media':    'inyoka.media.urls',
    'forum':    'inyoka.forum.urls',
    'admin':    'inyoka.admin.urls',
}

# The automatically generated reverse map
SUBDOMAIN_REVERSE_MAP = dict((v.split('.')[1], k) for k, v in
                             SUBDOMAIN_MAP.iteritems())

# this url conf is used for contrib stuff like the auth system
ROOT_URLCONF = 'inyoka.portal.urls'

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = False

# Absolute path to the directory that holds media and the URL
MEDIA_ROOT = join(BASE_PATH, 'media')
MEDIA_URL = 'http://media.%s' % BASE_DOMAIN_NAME

# same for static
STATIC_ROOT = join(BASE_PATH, 'static')
STATIC_URL = 'http://static.%s' % BASE_DOMAIN_NAME
ADMIN_MEDIA_PREFIX = STATIC_URL + '/_admin/'

# system settings
INYOKA_SYSTEM_USER = u'ubuntuusers.de'
INYOKA_SYSTEM_USER_EMAIL = 'system@' + BASE_DOMAIN_NAME

# path to the xapian database
XAPIAN_DATABASE = ''

# imagemagick path. leave empty for auto detection
IMAGEMAGICK_PATH = ''

# wiki settings
WIKI_MAIN_PAGE = 'Startseite'

# forum settings
FORUM_LIMIT_UNREAD = 10000

# the id of the ikhaya team group
IKHAYA_GROUP_ID = 1

# settings for the jabber bot
JABBER_BOT_SERVER = '127.0.0.1:6203'

# hours for a user to activate the account
ACTIVATION_HOURS = 48

# Signature length
SIGNATURE_LENGTH = 400
SIGNATURE_LINES = 4

# A tuple that defines the maximum avatar size
# define it as (width, height)
AVATAR_SIZE = (80, 100)

# key for google maps
GOOGLE_MAPS_APIKEY = ''

# The forum that should contain the wiki discussions
WIKI_DISCUSSION_FORUM = 'diskussionen'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'b)l0ju3erxs)od$g&l_0i1za^l+2dwgxuay(nwv$q4^*c#tdwt'

# Our Cache System. Set this to memcached or locmen or something
# more useful in the production environment
CACHE_BACKEND = 'locmem:///'

# We only load templates from the template folder
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.load_template_source',
    'django.template.loaders.app_directories.load_template_source'
)

MIDDLEWARE_CLASSES = (
    'inyoka.middlewares.session.AdvancedSessionMiddleware',
    'inyoka.middlewares.auth.AuthMiddleware',
    'django.middleware.doc.XViewMiddleware',
    'inyoka.middlewares.services.ServiceMiddleware',
    'inyoka.middlewares.common.CommonServicesMiddleware',
    'inyoka.middlewares.registry.RegistryMiddleware',
    'inyoka.middlewares.highlighter.HighlighterMiddleware'
)

TEMPLATE_DIRS = (
    join(BASE_PATH, 'templates'),
)

INSTALLED_APPS = (
    'django.contrib.contenttypes',
    'django.contrib.sites',
    'inyoka.portal',
    'inyoka.wiki',
    'inyoka.forum',
    'inyoka.ikhaya',
    'inyoka.pastebin',
    'inyoka.planet',
    'inyoka.admin',
)

# export only uppercase keys
__all__ = list(x for x in locals() if x.isupper())
