"""Common settings and globals."""
import datetime
import os
import platform
from logging.handlers import SysLogHandler
from os.path import basename, normpath
from sys import path

from oscar import OSCAR_MAIN_TEMPLATE_DIR

from ecommerce.settings._oscar import *

# PATH CONFIGURATION
# Absolute filesystem path to the Django project directory
DJANGO_ROOT = dirname(dirname(abspath(__file__)))

# Absolute filesystem path to the top-level project folder
SITE_ROOT = dirname(DJANGO_ROOT)

# Site name
SITE_NAME = basename(DJANGO_ROOT)

# Add our project to our pythonpath; this way, we don't need to type our project
# name in our dotted import paths
path.append(DJANGO_ROOT)
# END PATH CONFIGURATION


# DEBUG CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = False
# END DEBUG CONFIGURATION


# MANAGER CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#admins
ADMINS = (
    ('Your Name', 'your_email@example.com'),
)

# See: https://docs.djangoproject.com/en/dev/ref/settings/#managers
MANAGERS = ADMINS
# END MANAGER CONFIGURATION


# DATABASE CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#databases
# Note that we use connection pooling/persistent connections (CONN_MAX_AGE)
# in production, but the Django docs discourage its use in development.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.',
        'NAME': '',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
        'ATOMIC_REQUESTS': True,
    }
}
# END DATABASE CONFIGURATION


# GENERAL CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#time-zone
TIME_ZONE = 'America/New_York'

# See: https://docs.djangoproject.com/en/dev/ref/settings/#language-code
LANGUAGE_CODE = 'en-us'

# See: https://docs.djangoproject.com/en/dev/ref/settings/#site-id
# This needs to be set to None in order to support multitenancy
SITE_ID = None

# See: https://github.com/edx/edx-django-sites-extensions
DEFAULT_SITE_ID = 1

# See: https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True

LOCALE_PATHS = (
    join(DJANGO_ROOT, 'conf', 'locale'),
)

# See: https://docs.djangoproject.com/en/dev/ref/settings/#use-l10n
USE_L10N = True

# See: https://docs.djangoproject.com/en/dev/ref/settings/#use-tz
USE_TZ = True
# END GENERAL CONFIGURATION


# MEDIA CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#media-root
MEDIA_ROOT = normpath(join(SITE_ROOT, 'media'))

# See: https://docs.djangoproject.com/en/dev/ref/settings/#media-url
MEDIA_URL = '/media/'
# END MEDIA CONFIGURATION


# STATIC FILE CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#static-root
STATIC_ROOT = normpath(join(SITE_ROOT, 'assets'))

# See: https://docs.djangoproject.com/en/dev/ref/settings/#static-url
STATIC_URL = '/static/'

# See: https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#std:setting-STATICFILES_DIRS
STATICFILES_DIRS = (
    normpath(join(DJANGO_ROOT, 'static', 'build')),  # Check the r.js output directory first
    normpath(join(DJANGO_ROOT, 'static')),
)

# See: https://docs.djangoproject.com/en/dev/ref/contrib/staticfiles/#staticfiles-finders
# ThemeFilesFinder looks for static assets inside theme directories. It presents static assets according to the
# current theme. More details on ThemeFilesFinder can be seen at /ecommerce/theming/__init__.py
STATICFILES_FINDERS = (
    'ecommerce.theming.finders.ThemeFilesFinder',
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

# ThemeStorage stores and retrieves files with theming in mind.
# More details on ThemeStorage can be seen at /ecommerce/theming/__init__.py
STATICFILES_STORAGE = "ecommerce.theming.storage.ThemeStorage"

COMPRESS_PRECOMPILERS = (
    ('text/x-scss', 'django_libsass.SassCompiler'),
)

COMPRESS_CSS_FILTERS = ['compressor.filters.css_default.CssAbsoluteFilter']

COMPRESS_OFFLINE_CONTEXT = 'ecommerce.theming.compressor.offline_context'

# END STATIC FILE CONFIGURATION


# SECRET CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#secret-key
# Note: This key should only be used for development and testing.
SECRET_KEY = os.environ.get('ECOMMERCE_SECRET_KEY', 'insecure-secret-key')
# END SECRET CONFIGURATION


# SITE CONFIGURATION
# Hosts/domain names that are valid for this site
# See https://docs.djangoproject.com/en/1.5/ref/settings/#allowed-hosts
ALLOWED_HOSTS = []
# END SITE CONFIGURATION


# FIXTURE CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#std:setting-FIXTURE_DIRS
FIXTURE_DIRS = (
    normpath(join(SITE_ROOT, 'fixtures')),
)
# END FIXTURE CONFIGURATION


# TEMPLATE CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#template-context-processors
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': (
            normpath(join(DJANGO_ROOT, 'templates')),
            # Templates which override default Oscar templates
            normpath(join(DJANGO_ROOT, 'templates/oscar')),
            OSCAR_MAIN_TEMPLATE_DIR,
        ),
        'OPTIONS': {
            'loaders': [
                # ThemeTemplateLoader should come before any other loader to give theme templates
                # priority over system templates
                'ecommerce.theming.template_loaders.ThemeTemplateLoader',
                'django.template.loaders.app_directories.Loader',
            ],
            'context_processors': (
                'django.contrib.auth.context_processors.auth',
                'django.template.context_processors.debug',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.template.context_processors.tz',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.request',
                'oscar.apps.search.context_processors.search_form',
                'oscar.apps.promotions.context_processors.promotions',
                'oscar.apps.checkout.context_processors.checkout',
                'oscar.apps.customer.notifications.context_processors.notifications',
                'oscar.core.context_processors.metadata',
                'ecommerce.core.context_processors.core',
                'ecommerce.extensions.analytics.context_processors.analytics',
            ),
            'debug': True,  # Django will only display debug pages if the global DEBUG setting is set to True.
        }
    },
]
# END TEMPLATE CONFIGURATION


# MIDDLEWARE CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#middleware-classes
MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django_sites_extensions.middleware.CurrentSiteWithDefaultMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'waffle.middleware.WaffleMiddleware',
    # NOTE: The overridden BasketMiddleware relies on request.site. This middleware
    # MUST appear AFTER CurrentSiteMiddleware.
    'ecommerce.extensions.basket.middleware.BasketMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
    'social.apps.django_app.middleware.SocialAuthExceptionMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'threadlocals.middleware.ThreadLocalMiddleware',
    'ecommerce.theming.middleware.CurrentSiteThemeMiddleware',
    'ecommerce.theming.middleware.ThemePreviewMiddleware',
)
# END MIDDLEWARE CONFIGURATION


# URL CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = '{}.urls'.format(SITE_NAME)

# Commerce API settings used for publishing information to LMS.
COMMERCE_API_TIMEOUT = 7

# Cache course info from course API.
COURSES_API_CACHE_TIMEOUT = 3600  # Value is in seconds
PROGRAM_CACHE_TIMEOUT = 3600  # Value is in seconds.

# PROVIDER DATA PROCESSING
PROVIDER_DATA_PROCESSING_TIMEOUT = 15  # Value is in seconds.
CREDIT_PROVIDER_CACHE_TIMEOUT = 600
# END URL CONFIGURATION

VOUCHER_CACHE_TIMEOUT = 10  # Value is in seconds.

SDN_CHECK_REQUEST_TIMEOUT = 5  # Value is in seconds.

# APP CONFIGURATION
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.flatpages',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'widget_tweaks',
    'compressor',
    'rest_framework',
    'simple_history',
    'waffle',
    'django_filters',
    'rest_framework_swagger',
    'release_util',
    'crispy_forms',
    'solo',
]

# Apps specific to this project go here.
LOCAL_APPS = [
    'ecommerce.core',
    'ecommerce.coupons',
    'ecommerce.courses',
    'ecommerce.invoice',
    'ecommerce.referrals',

    # Theming app for customizing visual and behavioral attributes of a site
    'ecommerce.theming',

    # Sailthru email marketing integration
    'ecommerce.sailthru',

    # Enterprise app for ecommerce
    'ecommerce.enterprise',
]

# See: https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS + OSCAR_APPS
# END APP CONFIGURATION


# LOGGING CONFIGURATION
# Set up logging for development use (logging to stdout)
level = 'DEBUG' if DEBUG else 'INFO'
hostname = platform.node().split(".")[0]

# Use a different address for Mac OS X
syslog_address = '/var/run/syslog' if platform.system().lower() == 'darwin' else '/dev/log'
syslog_format = '[service_variant=ecommerce][%(name)s] %(levelname)s [{hostname}  %(process)d] ' \
                '[%(pathname)s:%(lineno)d] - %(message)s'.format(hostname=hostname)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s %(levelname)s %(process)d [%(name)s] %(pathname)s:%(lineno)d - %(message)s',
        },
        'syslog_format': {'format': syslog_format},
    },
    'handlers': {
        'console': {
            'level': level,
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout',
        },
        'local': {
            'level': level,
            'class': 'logging.handlers.SysLogHandler',
            'address': syslog_address,
            'formatter': 'syslog_format',
            'facility': SysLogHandler.LOG_LOCAL0,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'local'],
            'propagate': True,
            'level': 'INFO'
        },
        'requests': {
            'handlers': ['console', 'local'],
            'propagate': True,
            'level': 'WARNING'
        },
        'factory': {
            'handlers': ['console', 'local'],
            'propagate': True,
            'level': 'WARNING'
        },
        'elasticsearch': {
            'handlers': ['console', 'local'],
            'propagate': True,
            'level': 'WARNING'
        },
        'urllib3': {
            'handlers': ['console', 'local'],
            'propagate': True,
            'level': 'WARNING'
        },
        'django.request': {
            'handlers': ['console', 'local'],
            'propagate': True,
            'level': 'WARNING'
        },
        '': {
            'handlers': ['console', 'local'],
            'level': 'DEBUG',
            'propagate': False
        },
    }
}
# END LOGGING CONFIGURATION


# WSGI CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#wsgi-application
WSGI_APPLICATION = 'wsgi.application'
# END WSGI CONFIGURATION


# AUTHENTICATION
# Overrides user model used by Oscar. Oscar's default user model doesn't
# include a username field, instead using email addresses to uniquely identify
# users. In order to pair with the LMS, we need our users to have usernames,
# and since we don't need Oscar's custom logic for transferring user notifications,
# we can rely on a user model which subclasses Django's AbstractUser.
AUTH_USER_MODEL = 'core.User'

# See: http://getblimp.github.io/django-rest-framework-jwt/#additional-settings
JWT_AUTH = {
    'JWT_SECRET_KEY': None,
    'JWT_ALGORITHM': 'HS256',
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_LEEWAY': 1,
    'JWT_DECODE_HANDLER': 'ecommerce.extensions.api.handlers.jwt_decode_handler',
    # These settings are NOT part of DRF-JWT's defaults.
    'JWT_ISSUERS': (),
    # NOTE (CCB): This is temporarily set to False until we decide what values are acceptable.
    'JWT_VERIFY_AUDIENCE': False,
    'JWT_SECRET_KEYS': (),
}

# Service user for worker processes.
ECOMMERCE_SERVICE_WORKER_USERNAME = 'ecommerce_worker'

# Used to access the Enrollment API. Set this to the same value used by the LMS.
EDX_API_KEY = None

# Enables a special view that, when accessed, creates and logs in a new user.
# This should NOT be enabled for production deployments.
ENABLE_AUTO_AUTH = False

# Prefix for auto auth usernames. This value must be set in order for auto-auth to function.
# If it were not set, we would be unable to automatically remove all auto-auth users.
AUTO_AUTH_USERNAME_PREFIX = 'AUTO_AUTH_'

INSTALLED_APPS += ['social.apps.django_app.default']

AUTHENTICATION_BACKENDS = ('auth_backends.backends.EdXOpenIdConnect',) + AUTHENTICATION_BACKENDS

SOCIAL_AUTH_STRATEGY = 'ecommerce.social_auth.strategies.CurrentSiteDjangoStrategy'

# Set these to the correct values for your OAuth2/OpenID Connect provider
SOCIAL_AUTH_EDX_OIDC_KEY = None
SOCIAL_AUTH_EDX_OIDC_SECRET = None
SOCIAL_AUTH_EDX_OIDC_URL_ROOT = None
SOCIAL_AUTH_EDX_OIDC_LOGOUT_URL = None

# This value should be the same as SOCIAL_AUTH_EDX_OIDC_SECRET
SOCIAL_AUTH_EDX_OIDC_ID_TOKEN_DECRYPTION_KEY = SOCIAL_AUTH_EDX_OIDC_SECRET

# Redirect successfully authenticated users to the Oscar dashboard.
LOGIN_REDIRECT_URL = 'dashboard:index'
LOGIN_URL = 'login'

EXTRA_SCOPE = ['permissions']
# END AUTHENTICATION


# DJANGO REST FRAMEWORK
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'edx_rest_framework_extensions.authentication.JwtAuthentication',
        'ecommerce.extensions.api.authentication.BearerAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'ecommerce.extensions.api.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'user': '50/minute',
    },
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
    'TEST_REQUEST_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
}

SWAGGER_SETTINGS = {
    'info': {
        'title': 'edX E-Commerce API',
        'description': 'API for interacting with E-Commerce (Otto) orders, products, and associated resources.',
    },
    'doc_expansion': 'list',
    'api_version': 'v2',

    # Exclude the publication endpoint because its serializer requires context that rest-swagger does not
    # supply. See https://github.com/marcgibbons/django-rest-swagger/issues/397
    'exclude_namespaces': ['publication'],
}
# END DJANGO REST FRAMEWORK


# Resolving deprecation warning
TEST_RUNNER = 'django.test.runner.DiscoverRunner'


# COOKIE CONFIGURATION
# The purpose of customizing the cookie names is to avoid conflicts when
# multiple Django services are running behind the same hostname.
# Detailed information at: https://docs.djangoproject.com/en/dev/ref/settings/
SESSION_COOKIE_NAME = 'ecommerce_sessionid'
CSRF_COOKIE_NAME = 'ecommerce_csrftoken'
LANGUAGE_COOKIE_NAME = 'ecommerce_language'
# END COOKIE CONFIGURATION


# CELERY
# Default broker URL. See http://celery.readthedocs.io/en/latest/userguide/configuration.html#broker-url.
# In order for tasks to be visible to the ecommerce worker, this must match the value of BROKER_URL
# configured for the ecommerce worker!
BROKER_URL = None

# Disable connection pooling. Connections may be severed by load balancers.
# This forces the application to connect explicitly to the broker each time
# rather than assume a long-lived connection.
BROKER_POOL_LIMIT = 0
BROKER_CONNECTION_TIMEOUT = 1

# Use heartbeats to prevent broker connection loss. When the broker
# is behind a load balancer, the load balancer may timeout Celery's
# connection to the broker, causing messages to be lost.
BROKER_HEARTBEAT = 10.0
BROKER_HEARTBEAT_CHECKRATE = 2

# A sequence of modules to import when the worker starts.
# See http://celery.readthedocs.io/en/latest/userguide/configuration.html#imports.
CELERY_IMPORTS = (
    'ecommerce_worker.fulfillment.v1.tasks',
)

CELERY_ROUTES = {
    'ecommerce_worker.fulfillment.v1.tasks.fulfill_order': {'queue': 'fulfillment'},
    'ecommerce_worker.sailthru.v1.tasks.update_course_enrollment': {'queue': 'email_marketing'},
    'ecommerce_worker.sailthru.v1.tasks.send_course_refund_email': {'queue': 'email_marketing'},
}

# Prevent Celery from removing handlers on the root logger. Allows setting custom logging handlers.
# See http://celery.readthedocs.io/en/latest/userguide/configuration.html#worker-hijack-root-logger.
CELERYD_HIJACK_ROOT_LOGGER = False

# Execute tasks locally (synchronously) instead of sending them to the queue.
# See http://celery.readthedocs.io/en/latest/userguide/configuration.html#task-always-eager.
CELERY_ALWAYS_EAGER = False
# END CELERY


THEME_SCSS = 'sass/themes/default.scss'

# Path to the receipt page
RECEIPT_PAGE_PATH = '/checkout/receipt/'

# URL for Course Catalog service
COURSE_CATALOG_API_URL = 'http://localhost:8008/api/v1/'

# Black-listed course modes not allowed to create coupons with
BLACK_LIST_COUPON_COURSE_MODES = [u'audit', u'honor']

# Theme settings
# enable or disbale comprehensive theming
ENABLE_COMPREHENSIVE_THEMING = True

# name for waffle switch to use for disabling theming on runtime.
# Note: management command ignore this switch
DISABLE_THEMING_ON_RUNTIME_SWITCH = "disable_theming_on_runtime"

# Directory that contains all themes
COMPREHENSIVE_THEME_DIRS = [
    DJANGO_ROOT + "/themes",
]

# Theme to use when no site or site theme is defined,
# set to None if you want to use openedx theme
DEFAULT_SITE_THEME = None

# Cache time out for theme templates and related assets

THEME_CACHE_TIMEOUT = 30 * 60

# End Theme settings


EDX_DRF_EXTENSIONS = {
    'JWT_PAYLOAD_USER_ATTRIBUTE_MAPPING': {
        'administrator': 'is_staff',
        'email': 'email',
        'full_name': 'full_name',
        'tracking_context': 'tracking_context',
    },
}

# Enrollment codes voucher end datetime used for setting the end dates for vouchers
# created for the Enrollment code products.
ENROLLMENT_CODE_EXIPRATION_DATE = datetime.datetime.now() + datetime.timedelta(weeks=520)

# Affiliate cookie key
AFFILIATE_COOKIE_KEY = 'affiliate_id'

CRISPY_TEMPLATE_PACK = 'bootstrap3'

# ENTERPRISE APP CONFIGURATION
# URL for Enterprise service
ENTERPRISE_SERVICE_URL = 'http://localhost:8000/enterprise/'
# Cache enterprise response from Enterprise API.
ENTERPRISE_API_CACHE_TIMEOUT = 3600  # Value is in seconds

# Name for waffle switch to use for enabling enterprise features on runtime.
ENABLE_ENTERPRISE_ON_RUNTIME_SWITCH = 'enable_enterprise_on_runtime'
# END ENTERPRISE APP CONFIGURATION
