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

# per default there are no managers and admins.  I guess that's
# unused :)
MANAGERS = ADMINS = ()

# set the database settings in the actual settings file
DATABASE_NAME = DATABASE_USER = DATABASE_HOST = DATABASE_PORT = ''

# mysql only
DATABASE_ENGINE = 'mysql'
DATABASE_OPTIONS = {
    'init_command': "set storage_engine=INNODB"
}

# if we are in debug mode we issue tickets into a trac
TRAC_URL = 'http://trac.ubuntuusers.de/'
TRAC_USERNAME = 'ubuntu_de'
TRAC_PASSWORD = 'G3h31m!'


# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be avilable on all operating systems.
# the setting here has nothing to do with the timezone the user is
# using himself.  This is just because I don't know if not django
# will access this property in the ORM --- mitsuhiko
TIME_ZONE = 'UTC'

# Language code for this installation. All choices can be found here:
# http://www.w3.org/TR/REC-html40/struct/dirlang.html#langcodes
LANGUAGE_CODE = 'de-de'

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
USE_I18N = True

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

# the page below we have our templates.  The template the
# user specifies in the macro or in the parser is then
# joined with this page name according to our weird joining
# rules
WIKI_TEMPLATE_BASE = 'Wiki/Vorlagen'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'b)l0ju3erxs)od$g&l_0i1za^l+2dwgxuay(nwv$q4^*c#tdwt'

# if memcache servers are defined the caching system is initialized
# with the werkzeug memcache layer, otherwise the null cache.
MEMCACHE_SERVERS = []

MIDDLEWARE_CLASSES = (
    'django.middleware.gzip.GZipMiddleware',
    'inyoka.middlewares.session.AdvancedSessionMiddleware',
    'inyoka.middlewares.auth.AuthMiddleware',
    'inyoka.middlewares.registry.RegistryMiddleware',
    'inyoka.middlewares.services.ServiceMiddleware',
    'django.middleware.http.ConditionalGetMiddleware',
    'inyoka.middlewares.common.CommonServicesMiddleware',
    'inyoka.middlewares.highlighter.HighlighterMiddleware',
    'inyoka.middlewares.security.SecurityMiddleware'
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

# some terms to exclude by default to maintain readability
SEARCH_DEFAULT_EXCLUDE = ('Cstammtisch',)

# export only uppercase keys
__all__ = list(x for x in locals() if x.isupper())
