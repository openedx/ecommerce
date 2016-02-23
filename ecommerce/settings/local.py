"""Development settings and globals."""
from __future__ import absolute_import

import os
from os.path import join, normpath

from ecommerce.settings import get_lms_url
from ecommerce.settings.base import *
from ecommerce.settings.logger import get_logger_config


# DEBUG CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#debug
DEBUG = True
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
ECOMMERCE_URL_ROOT = 'http://localhost:8002'

LMS_URL_ROOT = 'http://localhost:8000'

# The location of the LMS heartbeat page
LMS_HEARTBEAT_URL = get_lms_url('/heartbeat')

# The location of the LMS student dashboard
LMS_DASHBOARD_URL = get_lms_url('/dashboard')

OAUTH2_PROVIDER_URL = get_lms_url('/oauth2')

COMMERCE_API_URL = get_lms_url('/api/commerce/v1/')
# END URL CONFIGURATION


# AUTHENTICATION
# Set these to the correct values for your OAuth2/OpenID Connect provider (e.g., devstack)
SOCIAL_AUTH_EDX_OIDC_KEY = 'f1a800994a803e570730'
SOCIAL_AUTH_EDX_OIDC_SECRET = 'aa0921bc886b02ff31304c3aa5d93bf04f872c5f'
SOCIAL_AUTH_EDX_OIDC_URL_ROOT = OAUTH2_PROVIDER_URL
SOCIAL_AUTH_EDX_OIDC_ID_TOKEN_DECRYPTION_KEY = SOCIAL_AUTH_EDX_OIDC_SECRET

JWT_AUTH.update({
    'JWT_SECRET_KEY': 'test',   # lms.ECOMMERCE_API_SIGNING_KEY
    'JWT_ISSUERS': (
        OAUTH2_PROVIDER_URL,
        # Must match the value of JWT_ISSUER configured for the ecommerce worker.
        'ecommerce_worker',
    ),
})
# END AUTHENTICATION


# ORDER PROCESSING
ENROLLMENT_API_URL = get_lms_url('/api/enrollment/v1/enrollment')
ENROLLMENT_FULFILLMENT_TIMEOUT = 15  # devstack is slow!

EDX_API_KEY = 'test'   # lms.EDX_API_KEY
# END ORDER PROCESSING

PAYMENT_PROCESSORS = (
    'ecommerce.extensions.payment.processors.paybox_system.PayboxSystem',
)
# PAYMENT PROCESSING
PAYMENT_PROCESSOR_CONFIG = {
    'paybox_system': {
        'PBX_SITE': '1999888',
        'PBX_RANG': '43',
        'PBX_IDENTIFIANT': '107975626',
        'PBX_REPONDRE_A': 'http://paybox.sleepy.cat:8080/payment/notification/',  #  TCP 80, 443 (HTTPS), 8080, 8081, 8082, 8083, 8084 ou 8085
        'private_key': '0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF',
        'payment_page_url': 'https://preprod-tpeweb.paybox.com/cgi/MYchoix_pagepaiement.cgi',
        'receipt_page_url': 'http://paybox.sleepy.cat:8000/payment/success/',
        'cancel_page_url': 'http://paybox.sleepy.cat:8000/payment/cancel/',
    },
}
# END PAYMENT PROCESSING


# CELERY
BROKER_URL = 'amqp://'

# Uncomment this to run tasks in-process (i.e., synchronously).
# CELERY_ALWAYS_EAGER = True
# END CELERY


ENABLE_AUTO_AUTH = True
LOGGING = get_logger_config(debug=DEBUG, dev_env=True, local_loglevel='DEBUG')

#####################################################################
# Lastly, see if the developer has any local overrides.
if os.path.isfile(join(dirname(abspath(__file__)), 'private.py')):
    from .private import *  # pylint: disable=import-error
