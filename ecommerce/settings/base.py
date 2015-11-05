"""Common settings and globals."""
import os
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
SITE_ID = 1

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
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'compressor.finders.CompressorFinder',
)

COMPRESS_PRECOMPILERS = (
    ('text/x-scss', 'django_libsass.SassCompiler'),
)

COMPRESS_CSS_FILTERS = ['compressor.filters.css_default.CssAbsoluteFilter']
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
        'APP_DIRS': True,
        'DIRS': (
            normpath(join(DJANGO_ROOT, 'templates')),
            # Templates which override default Oscar templates
            normpath(join(DJANGO_ROOT, 'templates/oscar')),
            OSCAR_MAIN_TEMPLATE_DIR,
        ),
        'OPTIONS': {
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
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.contrib.sites.middleware.CurrentSiteMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'waffle.middleware.WaffleMiddleware',
    'oscar.apps.basket.middleware.BasketMiddleware',
    'django.contrib.flatpages.middleware.FlatpageFallbackMiddleware',
    'social.apps.django_app.middleware.SocialAuthExceptionMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
)
# END MIDDLEWARE CONFIGURATION


# URL CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#root-urlconf
ROOT_URLCONF = '{}.urls'.format(SITE_NAME)

# Absolute URL used to construct URLs pointing back to the ecommerce service.
ECOMMERCE_URL_ROOT = None

# Absolute URL used to construct LMS URLs.
LMS_URL_ROOT = None

# The location of the LMS heartbeat page
LMS_HEARTBEAT_URL = None

# The location of the LMS student dashboard
LMS_DASHBOARD_URL = None

# URL to which enrollment requests should be made
ENROLLMENT_API_URL = None

# Commerce API settings used for publishing information to LMS.
COMMERCE_API_TIMEOUT = 7
COMMERCE_API_URL = None

# PROVIDER DATA PROCESSING
PROVIDER_DATA_PROCESSING_TIMEOUT = 15  # Value is in seconds.
CREDIT_PROVIDER_CACHE_TIMEOUT = 600

# OAuth2 provider URL used for OAuth2 transactions (e.g. validating access tokens)
OAUTH2_PROVIDER_URL = None
# END URL CONFIGURATION


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
    'django_filters'
]

# Apps specific to this project go here.
LOCAL_APPS = [
    'ecommerce.core',
    'ecommerce.courses',
    'ecommerce.invoice',
]

# See: https://docs.djangoproject.com/en/dev/ref/settings/#installed-apps
INSTALLED_APPS = DJANGO_APPS + LOCAL_APPS + OSCAR_APPS
# END APP CONFIGURATION


# LOGGING CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#logging
# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
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
    'JWT_DECODE_HANDLER': 'ecommerce.extensions.api.handlers.jwt_decode_handler',
    # This setting is not one of DRF-JWT's defaults.
    'JWT_ISSUERS': (),
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

# Set to true if using SSL and running behind a proxy
SOCIAL_AUTH_REDIRECT_IS_HTTPS = False

# https://github.com/omab/python-social-auth/blob/master/docs/configuration/django.rst#django-admin
SOCIAL_AUTH_ADMIN_USER_SEARCH_FIELDS = ['username', 'email']

SOCIAL_AUTH_PIPELINE = (
    'social.pipeline.social_auth.social_details',
    'social.pipeline.social_auth.social_uid',
    'social.pipeline.social_auth.auth_allowed',
    'social.pipeline.social_auth.social_user',

    # By default python-social-auth will simply create a new user/username if the username
    # from the provider conflicts with an existing username in this system. This custom pipeline function
    # loads existing users instead of creating new ones.
    'auth_backends.pipeline.get_user_if_exists',
    'social.pipeline.user.get_username',
    'social.pipeline.user.create_user',
    'social.pipeline.social_auth.associate_user',
    'social.pipeline.social_auth.load_extra_data',
    'social.pipeline.user.user_details'
)

# Fields passed to the custom ecommerce user model when creating a new user
SOCIAL_AUTH_USER_FIELDS = ['username', 'email', 'first_name', 'last_name']

# Always raise auth exceptions so that they are properly logged. Otherwise, the PSA middleware will redirect to an
# auth error page and attempt to display the error message to the user (via Django's message framework). We do not
# want the uer to see the message; but, we do want our downstream exception handlers to log the message.
SOCIAL_AUTH_RAISE_EXCEPTIONS = True

# Set these to the correct values for your OAuth2/OpenID Connect provider
SOCIAL_AUTH_EDX_OIDC_KEY = None
SOCIAL_AUTH_EDX_OIDC_SECRET = None
SOCIAL_AUTH_EDX_OIDC_URL_ROOT = None

# This value should be the same as SOCIAL_AUTH_EDX_OIDC_SECRET
SOCIAL_AUTH_EDX_OIDC_ID_TOKEN_DECRYPTION_KEY = SOCIAL_AUTH_EDX_OIDC_SECRET

# Redirect successfully authenticated users to the Oscar dashboard.
LOGIN_REDIRECT_URL = '/dashboard/'

EXTRA_SCOPE = ['permissions']
# END AUTHENTICATION


# ANALYTICS
# Specify a key to emit events to the corresponding Segment project. `None` disables tracking.
# See: https://segment.com/docs/libraries/python/
SEGMENT_KEY = None
# END ANALYTICS


# DJANGO REST FRAMEWORK
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'ecommerce.extensions.api.authentication.JwtAuthentication',
        'ecommerce.extensions.api.authentication.BearerAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'ecommerce.extensions.api.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'user': '40/minute',
    },
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
# Default broker URL. See http://celery.readthedocs.org/en/latest/configuration.html#broker-url.
# In order for tasks to be visible to the ecommerce worker, this must match the value of BROKER_URL
# configured for the ecommerce worker!
BROKER_URL = None

# A sequence of modules to import when the worker starts.
# See http://celery.readthedocs.org/en/latest/configuration.html#celery-imports.
CELERY_IMPORTS = (
    'ecommerce_worker.fulfillment.v1.tasks',
)

# Execute tasks locally (synchronously) instead of sending them to the queue.
# See http://celery.readthedocs.org/en/latest/configuration.html#celery-always-eager.
CELERY_ALWAYS_EAGER = False
# END CELERY


PLATFORM_NAME = 'Your Platform Name Here'
THEME_SCSS = 'sass/themes/default.scss'
