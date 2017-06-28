"""Development settings and globals."""
from __future__ import absolute_import

from urlparse import urljoin

from ecommerce.settings.base import *

# DEBUG CONFIGURATION
# See: https://docs.djangoproject.com/en/dev/ref/settings/#debug and
# https://docs.djangoproject.com/en/dev/ref/settings/#allowed-hosts
DEBUG = True
ALLOWED_HOSTS = ['*']
INTERNAL_IPS = ['127.0.0.1']
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

# AUTHENTICATION
SOCIAL_AUTH_REDIRECT_IS_HTTPS = False

JWT_AUTH.update({
    'JWT_SECRET_KEY': 'insecure-secret-key',
    'JWT_ISSUERS': (
        'http://127.0.0.1:8000/oauth2',
        # Must match the value of JWT_ISSUER configured for the ecommerce worker.
        'ecommerce_worker',
    ),
})
# END AUTHENTICATION


# ORDER PROCESSING
ENROLLMENT_FULFILLMENT_TIMEOUT = 15  # devstack is slow!

EDX_API_KEY = 'replace-me'
# END ORDER PROCESSING


# PAYMENT PROCESSING
PAYMENT_PROCESSOR_CONFIG = {
    'edx': {
        # NOTE: The same profile information is used here to appease the payment processor class.
        # Only Silent Order POST is actually used.
        'cybersource': {
            'merchant_id': 'edx_org',
            'transaction_key': '/yIJJejEGoNNcecTyxC9ZD0wR2ZjkkKuOaZnq2BGMGIGQIOKA1rBR009OuvKbPW4J1KLb15BMlaoiUXoj/8/Fp6dy33/aHAU0+yGKcEMxyYXQOBPKjuoChIlMRVkrtWZqP9shGxw1jwHNovmGrvd2ULRIn21Rsq6YnHie7lLLRhXyY2MjnFXfv75eH2rFwfi4hBPbVPvx/r8PwgFIh5otAzsgyIlBjaKJkzbNXd5qCOdNFSBcPcJps3YgVH0ASleI/SZp+Ckuyotd+EhzK0tOehPJAm3L03lkPNeFX9lcemuRkeV53V3nvobn3GaX0td4FAEe8CZBn+IpFC2PoK0tw==',
            'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.115.wsdl',
            'profile_id': '00D31C4B-4E8F-4E9F-A6B9-1DB8C7C86223',
            'access_key': '90a39534dc513e8a81222b158378dda1',
            'secret_key': 'ff09d545ddbe4f1e908cc47e3cceb30e4e9ff57a1fe0493392b69a0b75f8ac3df7840f89131d46faa4487071d53576d25047ebb39e9b4af18e9fb5ee1d4f1f66fdb711284c844c4c82bd24f168781e786ecf8b2d3dba4ab5b543c188ca5728e00b8ace43cca14cefbb605ecdc0706eda4cd50785d5754fd691426ddff03fcc7b',
            'payment_page_url': 'https://testsecureacceptance.cybersource.com/pay',
            'receipt_path': PAYMENT_PROCESSOR_RECEIPT_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'send_level_2_3_details': True,
            'sop_profile_id': '00D31C4B-4E8F-4E9F-A6B9-1DB8C7C86223',
            'sop_access_key': '90a39534dc513e8a81222b158378dda1',
            'sop_secret_key': 'ff09d545ddbe4f1e908cc47e3cceb30e4e9ff57a1fe0493392b69a0b75f8ac3df7840f89131d46faa4487071d53576d25047ebb39e9b4af18e9fb5ee1d4f1f66fdb711284c844c4c82bd24f168781e786ecf8b2d3dba4ab5b543c188ca5728e00b8ace43cca14cefbb605ecdc0706eda4cd50785d5754fd691426ddff03fcc7b',
            'sop_payment_page_url': 'https://testsecureacceptance.cybersource.com/silent/pay',
            'apple_pay_merchant_identifier': '',
            'apple_pay_merchant_id_domain_association': '',
            'apple_pay_merchant_id_certificate_path': '',
            'apple_pay_country_code': '',
        },
        'paypal': {
            'mode': 'sandbox',
            'client_id': 'AVcS4ZWEk7IPqaJibex3bCR0_lykVQ2BHdGz6JWVik0PKWGTOQzWMBOHRppPwFXMCPUqRsoBUDSE-ro5',
            'client_secret': 'EHNgP4mXL5mI54DQI1-EgXo6y0BDUzj5x1_8gQD0dNWSWS6pcLqlmGq8f5En6oos0z2L37a_EJ27mJ_a',
            'receipt_path': PAYMENT_PROCESSOR_RECEIPT_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'error_path': PAYMENT_PROCESSOR_ERROR_PATH,
        },
    },
}
# END PAYMENT PROCESSING


# CELERY
BROKER_URL = 'amqp://'

# Uncomment this to run tasks in-process (i.e., synchronously).
# CELERY_ALWAYS_EAGER = True
# END CELERY


ENABLE_AUTO_AUTH = True

#####################################################################
# Lastly, see if the developer has any local overrides.
if os.path.isfile(join(dirname(abspath(__file__)), 'private.py')):
    from .private import *  # pylint: disable=import-error

ENTERPRISE_API_URL = urljoin(ENTERPRISE_SERVICE_URL, 'api/v1/')
