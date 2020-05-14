"""Common settings and globals."""
from __future__ import absolute_import

import datetime
import os
import platform
from logging.handlers import SysLogHandler
from os.path import abspath, basename, dirname, join, normpath
from sys import path

from django.utils.translation import ugettext_lazy as _

from ecommerce.core.constants import (
    ENTERPRISE_COUPON_ADMIN_ROLE,
    ORDER_MANAGER_ROLE,
    STUDENT_SUPPORT_ADMIN_ROLE,
    SYSTEM_ENTERPRISE_ADMIN_ROLE,
    SYSTEM_ENTERPRISE_OPERATOR_ROLE
)
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
        'NAME': 'ecommerce',
        'USER': 'ecomm001',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '',
        'ATOMIC_REQUESTS': True,
        'CONN_MAX_AGE': 60,
    }
}
# END DATABASE CONFIGURATION


# GENERAL CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#time-zone
TIME_ZONE = 'UTC'

# See: https://docs.djangoproject.com/en/dev/ref/settings/#language-code
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en'

SITE_ID = 1

# See: https://docs.djangoproject.com/en/dev/ref/settings/#use-i18n
USE_I18N = True

LANGUAGES = (
    ('en', _('English')),
    ('es', _('Spanish')),
    ('es-419', _('Spanish (Latin American)')),
)

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
# See: https://docs.djangoproject.com/en/1.11/ref/settings/#middleware
MIDDLEWARE = (
    'corsheaders.middleware.CorsMiddleware',
    'edx_django_utils.cache.middleware.RequestCacheMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'edx_rest_framework_extensions.auth.jwt.middleware.JwtRedirectToLoginIfUnauthenticatedMiddleware',
    'edx_rest_framework_extensions.auth.jwt.middleware.JwtAuthCookieMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.contrib.sites.middleware.CurrentSiteMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'waffle.middleware.WaffleMiddleware',
    'ecommerce.extensions.analytics.middleware.TrackingMiddleware',
    # NOTE: The overridden BasketMiddleware relies on request.site. This middleware
    # MUST appear AFTER CurrentSiteMiddleware.
    'ecommerce.extensions.basket.middleware.BasketMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
    'social_django.middleware.SocialAuthExceptionMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'threadlocals.middleware.ThreadLocalMiddleware',
    'ecommerce.theming.middleware.CurrentSiteThemeMiddleware',
    'ecommerce.theming.middleware.ThemePreviewMiddleware',
    'edx_django_utils.cache.middleware.TieredCacheMiddleware',
    'edx_rest_framework_extensions.middleware.RequestMetricsMiddleware',
    'edx_rest_framework_extensions.auth.jwt.middleware.EnsureJWTAuthSettingsMiddleware',
    'crum.CurrentRequestUserMiddleware',
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

# Cache catalog results from the enterprise and discovery service.
CATALOG_RESULTS_CACHE_TIMEOUT = 86400

# Cache timeout for enterprise customer results from the enterprise service.
ENTERPRISE_CUSTOMER_RESULTS_CACHE_TIMEOUT = 3600  # Value is in seconds

# PROVIDER DATA PROCESSING
PROVIDER_DATA_PROCESSING_TIMEOUT = 15  # Value is in seconds.
CREDIT_PROVIDER_CACHE_TIMEOUT = 600

# Anonymous User Calculate Cache timeout
ANONYMOUS_BASKET_CALCULATE_CACHE_TIMEOUT = 3600  # Value is in seconds.

# LMS API settings used for fetching information from LMS
LMS_API_CACHE_TIMEOUT = 30  # Value is in seconds.
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
    'django.contrib.messages',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.staticfiles',
    'widget_tweaks',
    'compressor',
    'rest_framework',
    'waffle',
    'django_filters',
    'release_util',
    'crispy_forms',
    'solo',
    'social_django',
    'rest_framework_swagger',
    'rest_framework_datatables',
    'django_sites_extensions',
    # edx-drf-extensions
    'csrf.apps.CsrfAppConfig',  # Enables frontend apps to retrieve CSRF tokens.
    'rules.apps.AutodiscoverRulesConfig',
    'xss_utils',
]

# Apps specific to this project go here.
LOCAL_APPS = [
    'ecommerce.core',
    'ecommerce.coupons',
    'ecommerce.courses',
    'ecommerce.invoice',
    'ecommerce.bff',
    'ecommerce.programs',
    'ecommerce.referrals',
    'ecommerce.theming',
    'ecommerce.sailthru',
    'ecommerce.enterprise',
    'ecommerce.management',
    'ecommerce.journals',  # TODO: journals dependency
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
        'rules': {
            'handlers': ['console', 'local'],
            'level': 'DEBUG',
            'propagate': True,
        },
        '': {
            'handlers': ['console', 'local'],
            'level': 'DEBUG',
            'propagate': False
        },
    }
}

LOGGING_ROOT_OVERRIDES = {}
LOGGING_SUBSECTION_OVERRIDES = {}
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
    'JWT_SECRET_KEY': 'SET-ME-PLEASE',
    'JWT_ALGORITHM': 'HS256',
    'JWT_AUTH_COOKIE': 'edx-jwt-cookie',
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_LEEWAY': 1,
    'JWT_DECODE_HANDLER': 'ecommerce.extensions.api.handlers.jwt_decode_handler',
    # These settings are NOT part of DRF-JWT's defaults.
    'JWT_ISSUERS': [
        {
            'AUDIENCE': 'SET-ME-PLEASE',
            'ISSUER': 'http://127.0.0.1:8000/oauth2',
            'SECRET_KEY': 'SET-ME-PLEASE'
        },
        {
            'AUDIENCE': 'SET-ME-PLEASE',
            'ISSUER': 'ecommerce_worker',
            'SECRET_KEY': 'SET-ME-PLEASE'
        }
    ],
    # NOTE (CCB): This is temporarily set to False until we decide what values are acceptable.
    'JWT_VERIFY_AUDIENCE': False,
    'JWT_PUBLIC_SIGNING_JWK_SET': None,
    'JWT_AUTH_COOKIE_HEADER_PAYLOAD': 'edx-jwt-cookie-header-payload',
    'JWT_AUTH_COOKIE_SIGNATURE': 'edx-jwt-cookie-signature',
    'JWT_AUTH_HEADER_PREFIX': 'JWT',
}

# Service user for worker processes.
ECOMMERCE_SERVICE_WORKER_USERNAME = 'ecommerce_worker'

# Worker user used by prospectus to query ecommerce
PROSPECTUS_WORKER_USERNAME = 'prospectus_worker'

# Used to access the Enrollment API. Set this to the same value used by the LMS.
EDX_API_KEY = 'PUT_YOUR_API_KEY_HERE'

# Enables a special view that, when accessed, creates and logs in a new user.
# This should NOT be enabled for production deployments.
ENABLE_AUTO_AUTH = False

# Prefix for auto auth usernames. This value must be set in order for auto-auth to function.
# If it were not set, we would be unable to automatically remove all auto-auth users.
AUTO_AUTH_USERNAME_PREFIX = 'AUTO_AUTH_'

AUTHENTICATION_BACKENDS = ('auth_backends.backends.EdXOAuth2',) + AUTHENTICATION_BACKENDS

SOCIAL_AUTH_STRATEGY = 'ecommerce.social_auth.strategies.CurrentSiteDjangoStrategy'

# Set these to the correct values for your OAuth2 provider
SOCIAL_AUTH_EDX_OAUTH2_KEY = "ecommerce-sso-key"
SOCIAL_AUTH_EDX_OAUTH2_SECRET = "ecommerce-sso-secret"
SOCIAL_AUTH_EDX_OAUTH2_ISSUER = "http://127.0.0.1:8000"
SOCIAL_AUTH_EDX_OAUTH2_URL_ROOT = "http://127.0.0.1:8000"
SOCIAL_AUTH_EDX_OAUTH2_LOGOUT_URL = "http://127.0.0.1:8000/logout"

# Redirect successfully authenticated users to the Oscar dashboard.
LOGIN_REDIRECT_URL = 'dashboard:index'
LOGIN_URL = 'login'

EXTRA_SCOPE = ['permissions']
# END AUTHENTICATION


# DJANGO REST FRAMEWORK
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'edx_rest_framework_extensions.auth.jwt.authentication.JwtAuthentication',
        'ecommerce.extensions.api.authentication.BearerAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'ecommerce.extensions.api.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'user': '75/minute',
    },
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
    'TEST_REQUEST_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework_datatables.renderers.DatatablesRenderer',
        'rest_framework_csv.renderers.CSVRenderer',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'rest_framework_datatables.filters.DatatablesFilterBackend',
    ),
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema'
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
CSRF_COOKIE_SECURE = False
LANGUAGE_COOKIE_NAME = 'openedx-language-preference'
SESSION_COOKIE_SECURE = False
# END COOKIE CONFIGURATION


# CELERY
# Default broker URL. See http://celery.readthedocs.io/en/latest/userguide/configuration.html#broker-url.
# In order for tasks to be visible to the ecommerce worker, this must match the value of BROKER_URL
# configured for the ecommerce worker!
BROKER_URL = 'amqp://celery:celery@127.0.0.1:5672'

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

DEFAULT_PRIORITY_QUEUE = 'ecommerce.default'
CELERY_DEFAULT_EXCHANGE = 'ecommerce'
CELERY_DEFAULT_ROUTING_KEY = 'ecommerce'
CELERY_DEFAULT_QUEUE = DEFAULT_PRIORITY_QUEUE
CELERY_ROUTES = {
    'ecommerce_worker.fulfillment.v1.tasks.fulfill_order': {'queue': 'ecommerce.fulfillment'},
    'ecommerce_worker.sailthru.v1.tasks.update_course_enrollment': {'queue': 'ecommerce.email_marketing'},
    'ecommerce_worker.sailthru.v1.tasks.send_course_refund_email': {'queue': 'ecommerce.email_marketing'},
    'ecommerce_worker.sailthru.v1.tasks.send_offer_assignment_email': {'queue': 'ecommerce.email_marketing'},
    'ecommerce_worker.sailthru.v1.tasks.send_offer_update_email': {'queue': 'ecommerce.email_marketing'},
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

# URL for Discovery Service
COURSE_CATALOG_API_URL = 'http://localhost:8008/api/v1/'

# Black-listed course modes not allowed to create coupons with
BLACK_LIST_COUPON_COURSE_MODES = [u'audit', u'honor']

# Theme settings
# enable or disable comprehensive theming
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
        'user_id': 'lms_user_id',
    },
    'JWT_PAYLOAD_MERGEABLE_USER_ATTRIBUTES': (
        'tracking_context',
    ),
    'OAUTH2_USER_INFO_URL': 'http://127.0.0.1:8000/oauth2/user_info',
    'ENABLE_SET_REQUEST_USER_FOR_JWT_COOKIE': True,
}

# Enrollment codes voucher end datetime used for setting the end dates for vouchers
# created for the Enrollment code products.
ENROLLMENT_CODE_EXIPRATION_DATE = datetime.datetime.now() + datetime.timedelta(weeks=520)
ENROLLMENT_FULFILLMENT_TIMEOUT = 7

# Affiliate cookie key
AFFILIATE_COOKIE_KEY = 'affiliate_id'

CRISPY_TEMPLATE_PACK = 'bootstrap3'

# ENTERPRISE CONFIGURATION
# URL for Enterprise service
ENTERPRISE_SERVICE_URL = 'http://localhost:8000/enterprise/'
# Cache enterprise response from Enterprise API.
ENTERPRISE_API_CACHE_TIMEOUT = 300  # Value is in seconds

ENTERPRISE_CATALOG_SERVICE_URL = 'http://localhost:18160/'

ENTERPRISE_LEARNER_PORTAL_HOSTNAME = os.environ.get('ENTERPRISE_LEARNER_PORTAL_HOSTNAME', 'localhost:8734')

# Name for waffle switch to use for enabling enterprise features on runtime.
ENABLE_ENTERPRISE_ON_RUNTIME_SWITCH = 'enable_enterprise_on_runtime'

ENTERPRISE_CUSTOMER_COOKIE_NAME = 'enterprise_customer_uuid'

ENTERPRISE_DATA_API_GROUP = 'enterprise_data_api_access'

# List of enterprise customer uuids to exclude from transition to use of enterprise-catalog
ENTERPRISE_CUSTOMERS_EXCLUDED_FROM_CATALOG = []

SYSTEM_TO_FEATURE_ROLE_MAPPING = {
    SYSTEM_ENTERPRISE_ADMIN_ROLE: [ENTERPRISE_COUPON_ADMIN_ROLE],
    SYSTEM_ENTERPRISE_OPERATOR_ROLE: [ENTERPRISE_COUPON_ADMIN_ROLE],
    STUDENT_SUPPORT_ADMIN_ROLE: [ORDER_MANAGER_ROLE],
}

# END ENTERPRISE CONFIGURATION

# DJANGO DEBUG TOOLBAR CONFIGURATION
# http://django-debug-toolbar.readthedocs.org/en/latest/installation.html
if os.environ.get('ENABLE_DJANGO_TOOLBAR', False):
    INSTALLED_APPS += [
        'debug_toolbar',
    ]

    MIDDLEWARE += (
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    )

# Determines if events are actually sent to Segment. This should only be set to False for testing purposes.
SEND_SEGMENT_EVENTS = True

NEW_CODES_EMAIL_CONFIG = {
    'email_subject': 'New edX codes available',
    'from_email': 'customersuccess@edx.org',
    'email_body': '''
        Hello,

        This message is to inform you that a new order has been processed for your organization. Please visit the
        following page, in your Admin Dashboard, to find new codes ready for use.

        https://portal.edx.org/{enterprise_slug}/admin/coupons

        Having trouble accessing your codes? Please contact edX Enterprise Support at customersuccess@edx.org.
        Thank you.
    '''
}

OFFER_ASSIGNMENT_EMAIL_TEMPLATE = '''
You may redeem this code for {REDEMPTIONS_REMAINING} course(s).

edX Login: {USER_EMAIL}
Access Code: {CODE}
Expiration Date: {EXPIRATION_DATE}
'''
OFFER_ASSIGNMENT_EMAIL_SUBJECT = 'New edX course assignment'

OFFER_REVOKE_EMAIL_TEMPLATE = '''
Your Learning Manager has revoked access code {CODE} and it is no longer assigned to your edX account {USER_EMAIL}.
'''
OFFER_REVOKE_EMAIL_SUBJECT = 'edX Course Assignment Revoked'

OFFER_REMINDER_EMAIL_TEMPLATE = '''
You have redeemed this code {REDEEMED_OFFER_COUNT} time(s) out of {TOTAL_OFFER_COUNT} available course redemptions.

edX Login: {USER_EMAIL}
Access Code: {CODE}
Expiration Date: {EXPIRATION_DATE}
'''
OFFER_REMINDER_EMAIL_SUBJECT = 'Reminder on edX course assignment'

OFFER_ASSIGNMEN_EMAIL_TEMPLATE_BODY_MAP = {
    'assign': OFFER_ASSIGNMENT_EMAIL_TEMPLATE,
    'revoke': OFFER_REVOKE_EMAIL_TEMPLATE,
    'remind': OFFER_REMINDER_EMAIL_TEMPLATE,
}

# SAILTHRU settings
SAILTHRU_KEY = 'sailthru key here'
SAILTHRU_SECRET = 'sailthru secret here'

USERNAME_REPLACEMENT_WORKER = "replace with valid username"

CORS_ALLOW_CREDENTIALS = False
ECOMMERCE_URL_ROOT = "http://localhost:8002"
OSCAR_FROM_EMAIL = 'oscar@example.com'
OSCAR_SLUG_ALLOW_UNICODE = True
PLATFORM_NAME = 'Your Platform Name Here'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SOCIAL_AUTH_REDIRECT_IS_HTTPS = False

CORS_ORIGIN_WHITELIST = []
CORS_URLS_REGEX = ''

ECOMMERCE_PAYMENT_PROCESSOR_CONFIG = {
    'edx': {
        'cybersource': {
            'access_key': 'SET-ME-PLEASE',
            'apple_pay_country_code': 'US',
            'apple_pay_merchant_id_certificate_path': '/edx/etc/ssl/apple_pay_merchant.pem',
            'apple_pay_merchant_id_domain_association': 'This value should also be in private configuration. '
                                                        'It, too,\nwill span multiple lines.',
            'apple_pay_merchant_identifier': 'merchant.com.example',
            'cancel_page_url': '/checkout/cancel-checkout/',
            'merchant_id': 'SET-ME-PLEASE',
            'payment_page_url': 'https://testsecureacceptance.cybersource.com/pay',
            'profile_id': 'SET-ME-PLEASE',
            'receipt_page_url': '/checkout/receipt/',
            'secret_key':  'SET-ME-PLEASE',
            'send_level_2_3_details': True,
            'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/'
                            'CyberSourceTransaction_1.140.wsdl',
            'sop_access_key': 'SET-ME-PLEASE',
            'sop_payment_page_url': 'https://testsecureacceptance.cybersource.com/silent/pay',
            'sop_profile_id': 'SET-ME-PLEASE',
            'sop_secret_key': 'SET-ME-PLEASE',
            'transaction_key': 'SET-ME-PLEASE'
        },
        'paypal': {
            'cancel_checkout_path': '/checkout/cancel-checkout/',
            'client_id': 'SET-ME-PLEASE',
            'client_secret': 'SET-ME-PLEASE',
            'error_url': '/checkout/error/',
            'mode': 'sandbox',
            'receipt_url': '/checkout/receipt/'
        }
    }
}
MEDIA_STORAGE_BACKEND = {
    'DEFAULT_FILE_STORAGE': 'django.core.files.storage.FileSystemStorage',
    'MEDIA_ROOT': MEDIA_ROOT,
    'MEDIA_URL': MEDIA_URL
}
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
BACKEND_SERVICE_EDX_OAUTH2_KEY = "ecommerce-backend-service-key"
BACKEND_SERVICE_EDX_OAUTH2_SECRET = "ecommerce-backend-service-secret"
BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL = "http://127.0.0.1:8000/oauth2"
EXTRA_APPS = []
API_ROOT = None

# Needed to link to the payment micro-frontend
PAYMENT_MICROFRONTEND_URL = None

# For Enterprise purchases to send purchase information to HubSpot for marketing leads
HUBSPOT_FORMS_API_URI = "SET-ME-PLEASE"
HUBSPOT_PORTAL_ID = "SET-ME-PLEASE"
HUBSPOT_SALES_LEAD_FORM_GUID = "SET-ME-PLEASE"

# To check government purchase restriction lists
SDN_CHECK_API_URL ="https://api.trade.gov/gateway/v1/consolidated_screening_list/search"
SDN_CHECK_API_KEY = "sdn search key here"
