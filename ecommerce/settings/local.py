"""Development settings and globals."""
from __future__ import absolute_import

import os
from os.path import join, normpath

from ecommerce.settings.base import *
from ecommerce.settings.logger import get_logger_config


# DEBUG CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True

# See: https://docs.djangoproject.com/en/dev/ref/settings/#template-debug
TEMPLATE_DEBUG = DEBUG
# END DEBUG CONFIGURATION


# EMAIL CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#email-backend
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# END EMAIL CONFIGURATION


# DATABASE CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': normpath(join(DJANGO_ROOT, 'default.db')),
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
        'ATOMIC_REQUESTS': True,
    }
}
# END DATABASE CONFIGURATION


# CACHE CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#caches
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
# END CACHE CONFIGURATION


# TOOLBAR CONFIGURATION
# See: http://django-debug-toolbar.readthedocs.org/en/latest/installation.html#explicit-setup
if os.environ.get('ENABLE_DJANGO_TOOLBAR', False):
    INSTALLED_APPS += (
        'debug_toolbar',
    )

    MIDDLEWARE_CLASSES += (
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    )

    DEBUG_TOOLBAR_PATCH_SETTINGS = False

# http://django-debug-toolbar.readthedocs.org/en/latest/installation.html
INTERNAL_IPS = ('127.0.0.1',)
# END TOOLBAR CONFIGURATION


# URL CONFIGURATION
# Do not include a trailing slash.
LMS_URL_ROOT = 'http://127.0.0.1:8000'


def get_lms_url(path):
    return LMS_URL_ROOT + path

# The location of the LMS heartbeat page
LMS_HEARTBEAT_URL = get_lms_url('/heartbeat')

# The location of the LMS student dashboard
LMS_DASHBOARD_URL = get_lms_url('/dashboard')

OAUTH2_PROVIDER_URL = get_lms_url('/oauth2')
# END URL CONFIGURATION


# AUTHENTICATION
# Set these to the correct values for your OAuth2/OpenID Connect provider (e.g., devstack)
SOCIAL_AUTH_EDX_OIDC_KEY = 'replace-me'
SOCIAL_AUTH_EDX_OIDC_SECRET = 'replace-me'
SOCIAL_AUTH_EDX_OIDC_URL_ROOT = OAUTH2_PROVIDER_URL
SOCIAL_AUTH_EDX_OIDC_ID_TOKEN_DECRYPTION_KEY = SOCIAL_AUTH_EDX_OIDC_SECRET

JWT_AUTH['JWT_SECRET_KEY'] = 'insecure-secret-key'
# END AUTHENTICATION


# ORDER PROCESSING
ENROLLMENT_API_URL = get_lms_url('/api/enrollment/v1/enrollment')
ENROLLMENT_FULFILLMENT_TIMEOUT = 15     # devstack is slow!

EDX_API_KEY = 'replace-me'
# END ORDER PROCESSING


# PAYMENT PROCESSING
PAYMENT_PROCESSOR_CONFIG = {
    'cybersource': {
        'profile_id': 'fake-profile-id',
        'access_key': 'fake-access-key',
        'secret_key': 'fake-secret-key',
        'payment_page_url': 'https://replace-me/',
        'receipt_page_url': get_lms_url('/commerce/checkout/receipt/'),
        'cancel_page_url': get_lms_url('/commerce/checkout/cancel/')
    }
}
# END PAYMENT PROCESSING


ENABLE_AUTO_AUTH = True
LOGGING = get_logger_config(debug=DEBUG, dev_env=True, local_loglevel='DEBUG')
