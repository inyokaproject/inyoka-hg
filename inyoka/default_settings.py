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

# debug mode is off by default
DEBUG = False
DEBUG_LEAK = False
DATABASE_DEBUG = False
DEVSERVER_HOST = 'localhost'
DEVSERVER_PORT = 8080

# so is the code execution debugger.  never enable on production
ENABLE_DEBUGGER = False

# enable logging to trac. Maybe only for development use...
ENABLE_TRAC_LOGGING = True

# template caching.  If none the templates will be cached if the
# debug stuff is disabled
TEMPLATE_CACHING = None

# per default there are no managers and admins.  I guess that's
# unused :)
MANAGERS = ADMINS = ()

# set the database settings in the actual settings file
DATABASE_NAME = DATABASE_USER = DATABASE_HOST = DATABASE_PORT = ''

# mysql only
DATABASE_ENGINE = 'mysql'

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
    'forum':    'inyoka.forum.urls',
    'admin':    'inyoka.admin.urls',
}

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

# trac data
TRAC_URL = None
TRAC_USERNAME = None
TRAC_PASSWORD = None

# system settings
INYOKA_SYSTEM_USER = u'ubuntuusers.de'
INYOKA_SYSTEM_USER_EMAIL = 'system@' + BASE_DOMAIN_NAME
INYOKA_SYSTEM_USER_EMAIL = None

# use etags
USE_ETAGS = True

# prefix for the system mails
EMAIL_SUBJECT_PREFIX = u'ubuntuusers: '

# path to the xapian database
XAPIAN_DATABASE = join(BASE_PATH, 'inyoka.xapdb')

# imagemagick path. leave empty for auto detection
IMAGEMAGICK_PATH = ''

# forum settings
FORUM_LIMIT_UNREAD = 100
FORUM_TOPIC_CACHE = 100
FORUM_THUMBNAIL_SIZE = (64, 64)
# time in seconds after posting a user is allowed to edit/delete his own posts,
# for posts (without, with) replies. -1 for infinitely, 0 for never
FORUM_OWNPOST_EDIT_LIMIT = (-1, 43200)
FORUM_OWNPOST_DELETE_LIMIT = (86400, 0)

# the id of the ikhaya team group
IKHAYA_GROUP_ID = 1

# settings for the jabber bot
JABBER_BOT_SERVER = '127.0.0.1:6203'

# hours for a user to activate the account
ACTIVATION_HOURS = 48

# days to describe an inactive user
USER_INACTIVE_DAYS = 365

# key for google maps
GOOGLE_MAPS_APIKEY = ''

# wiki settings
WIKI_MAIN_PAGE = 'Startseite'

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
# a prefix that is automatically added on every cache operation to the key.
# You won't notice anything of it at all but it makes it possible to run more
# than one application on a single memcached server without the risk of cache
# key collision.
CACHE_PREFIX = 'ubuntu_de/'

MIDDLEWARE_CLASSES = (
    'inyoka.middlewares.common.CommonServicesMiddleware',
    'inyoka.middlewares.session.AdvancedSessionMiddleware',
    'inyoka.middlewares.auth.AuthMiddleware',
    'django.middleware.transaction.TransactionMiddleware',
    'inyoka.middlewares.services.ServiceMiddleware',
    'django.middleware.http.ConditionalGetMiddleware',
    'inyoka.middlewares.highlighter.HighlighterMiddleware',
    'inyoka.middlewares.security.SecurityMiddleware',
    'inyoka.middlewares.profiler.MemoryProfilerMiddleware',
)

# Only upload via memory and just 2.5mb, until we kick django
FILE_UPLOAD_HANDLERS = ('django.core.files.uploadhandler.MemoryFileUploadHandler',)

TEMPLATE_DIRS = (
    join(BASE_PATH, 'templates'),
)

INSTALLED_APPS = (
    'inyoka.portal',
    'inyoka.wiki',
    'inyoka.forum',
    'inyoka.ikhaya',
    'inyoka.pastebin',
    'inyoka.planet',
    'inyoka.admin',
)

# some terms to exclude by default to maintain readability
SEARCH_DEFAULT_EXCLUDE = ['Cstammtisch',]

# All media directories inyoka requires
MEDIA_DIRS = ['forum', 'forum/attachments', 'forum/attachments/temp',
              'forum/thumbnails', 'planet', 'planet/icons', 'media/wiki',
              'wiki/attachments', 'media/portal', 'portal/avatars',
              'portal/team_icons']

# export only uppercase keys
__all__ = list(x for x in locals() if x.isupper())
