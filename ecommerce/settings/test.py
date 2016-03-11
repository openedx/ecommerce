from __future__ import absolute_import

from django.conf import settings

from ecommerce.settings import get_lms_url
from ecommerce.settings.base import *
from ecommerce.settings.logger import get_logger_config


# TEST SETTINGS
INSTALLED_APPS += (
    'django_nose',
)

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'

LOGGING = get_logger_config(debug=DEBUG, dev_env=True, local_loglevel='DEBUG')

if os.getenv('DISABLE_MIGRATIONS'):

    class DisableMigrations(object):

        def __contains__(self, item):
            return True

        def __getitem__(self, item):
            return "notmigrations"


    MIGRATION_MODULES = DisableMigrations()
# END TEST SETTINGS


# IN-MEMORY TEST DATABASE
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
        'ATOMIC_REQUESTS': True,
    },
}
# END IN-MEMORY TEST DATABASE


# URL CONFIGURATION
ECOMMERCE_URL_ROOT = 'http://localhost:8002'

LMS_URL_ROOT = 'http://127.0.0.1:8000'

# The location of the LMS heartbeat page
LMS_HEARTBEAT_URL = get_lms_url('/heartbeat')

# The location of the LMS student dashboard
LMS_DASHBOARD_URL = get_lms_url('/dashboard')

COMMERCE_API_URL = get_lms_url('/api/commerce/v1/')
# END URL CONFIGURATION


# AUTHENTICATION
ENABLE_AUTO_AUTH = True

JWT_AUTH.update({
    'JWT_SECRET_KEY': 'insecure-secret-key',
    'JWT_ISSUERS': ('test-issuer',),
})

PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
)
# END AUTHENTICATION


# ORDER PROCESSING
ENROLLMENT_API_URL = LMS_URL_ROOT + '/api/enrollment/v1/enrollment'

EDX_API_KEY = 'replace-me'
# END ORDER PROCESSING


# PAYMENT PROCESSING
PAYMENT_PROCESSOR_CONFIG = {
    'cybersource': {
        'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.115.wsdl',
        'merchant_id': 'fake-merchant-id',
        'transaction_key': 'fake-transaction-key',
        'profile_id': 'fake-profile-id',
        'access_key': 'fake-access-key',
        'secret_key': 'fake-secret-key',
        'payment_page_url': 'https://replace-me/',
        'receipt_page_url': get_lms_url(settings.RECEIPT_PAGE_PATH),
        'cancel_page_url': get_lms_url('/commerce/checkout/cancel/'),
    },
    'paypal': {
        'mode': 'sandbox',
        'client_id': 'fake-client-id',
        'client_secret': 'fake-client-secret',
        'receipt_url': get_lms_url(settings.RECEIPT_PAGE_PATH),
        'cancel_url': get_lms_url('/commerce/checkout/cancel/'),
        'error_url': get_lms_url('/commerce/checkout/error/'),
    },
    'stripe': {
        'publishable_key': 'fake',
        'secret_key': 'fake',
        'receipt_page_url': get_lms_url('/commerce/checkout/receipt/'),
        'image_url': '/static/images/default-theme/logo.png',
    },
}
# END PAYMENT PROCESSING


# CELERY
# Run tasks in-process, without sending them to the queue (i.e., synchronously).
CELERY_ALWAYS_EAGER = True
# END CELERY


# Use production settings for asset compression so that asset compilation can be tested on the CI server.
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
