"""Development settings and globals."""


from urllib.parse import urljoin

from corsheaders.defaults import default_headers as corsheaders_default_headers

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
    'JWT_ISSUERS': [
        {
            'SECRET_KEY': 'lms-secret',
            'AUDIENCE': 'lms-key',
            'ISSUER': 'http://edx.devstack.lms:18000/oauth2'
        },
        {
            # TODO: ARCH-276: Remove this second issuer once we are no longer
            # using multiple issuers.
            'SECRET_KEY': 'insecure-secret-key',
            # NOTE: This value of AUDIENCE doesn't make sense, even for the
            # LMS, but we are just making it match for now until AUDIENCE is
            # potentially removed altogether.
            'AUDIENCE': 'lms-key',
            # Must match the value of JWT_ISSUER configured for the ecommerce worker.
            'ISSUER': 'ecommerce_worker'
        },
    ],
    'JWT_PUBLIC_SIGNING_JWK_SET': (
        '{"keys": [{"kid": "devstack_key", "e": "AQAB", "kty": "RSA", "n": "smKFSYowG6nNUAdeqH1jQQnH1PmIHphzBmwJ5vRf1vu'
        '48BUI5VcVtUWIPqzRK_LDSlZYh9D0YFL0ZTxIrlb6Tn3Xz7pYvpIAeYuQv3_H5p8tbz7Fb8r63c1828wXPITVTv8f7oxx5W3lFFgpFAyYMmROC'
        '4Ee9qG5T38LFe8_oAuFCEntimWxN9F3P-FJQy43TL7wG54WodgiM0EgzkeLr5K6cDnyckWjTuZbWI-4ffcTgTZsL_Kq1owa_J2ngEfxMCObnzG'
        'y5ZLcTUomo4rZLjghVpq6KZxfS6I1Vz79ZsMVUWEdXOYePCKKsrQG20ogQEkmTf9FT_SouC6jPcHLXw"}]}'
    ),
})

CORS_ORIGIN_WHITELIST = (
    'http://localhost:1991' # Enterprise Admin Portal MFE
)
CORS_ALLOW_HEADERS = corsheaders_default_headers + (
    'use-jwt-cookie',
)
CORS_ALLOW_CREDENTIALS = True

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
            'transaction_key': '2iJRV1OoAiMxSsFRQfkmdeqYKzwV76R5AY7vs/zKCQf2Dy0gYsno6sEizavo9rz29kcq/s2F+nGP0DrNNwDXyAxI3FW77HY+0jAssnXwd8cW1Pt5aEBcQvnOQ4i9nbN2mr1XJ+MthRbNodz1FgLFuTiZenpjFq1DFmQwFi2u7V1ItQrmG19kvnpk1++mZ8Dx7s4GdN8jxdvesNGoKo7E05X6LZTHdUCP3rfq/1Nn4RDoPvxtv9UMe77yxtUF8LVJ8clAl4VyW+6uhmgfIWninfQiESR0HQ++cNJS1EXHjwNyuDEdEALKxAwgUu4DQpFbTD1bcRRm4VrnDr6MsA8NaA==',
            'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.166.wsdl',
            'receipt_path': PAYMENT_PROCESSOR_RECEIPT_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'send_level_2_3_details': True,
            'apple_pay_merchant_identifier': '',
            'apple_pay_merchant_id_domain_association': '',
            'apple_pay_merchant_id_certificate_path': '',
            'apple_pay_country_code': '',
        },
        'cybersource-rest': {
            'merchant_id': 'edx_org',
            'transaction_key': '2iJRV1OoAiMxSsFRQfkmdeqYKzwV76R5AY7vs/zKCQf2Dy0gYsno6sEizavo9rz29kcq/s2F+nGP0DrNNwDXyAxI3FW77HY+0jAssnXwd8cW1Pt5aEBcQvnOQ4i9nbN2mr1XJ+MthRbNodz1FgLFuTiZenpjFq1DFmQwFi2u7V1ItQrmG19kvnpk1++mZ8Dx7s4GdN8jxdvesNGoKo7E05X6LZTHdUCP3rfq/1Nn4RDoPvxtv9UMe77yxtUF8LVJ8clAl4VyW+6uhmgfIWninfQiESR0HQ++cNJS1EXHjwNyuDEdEALKxAwgUu4DQpFbTD1bcRRm4VrnDr6MsA8NaA==',
            'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.166.wsdl',
            'receipt_path': PAYMENT_PROCESSOR_RECEIPT_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'send_level_2_3_details': True,
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
        'stripe': {
            'api_version': '2022-08-01; server_side_confirmation_beta=v1',
            'enable_telemetry': None,
            'log_level': 'debug',
            'max_network_retries': 0,
            'proxy': None,
            'publishable_key': 'SET-ME-PLEASE',
            'secret_key': 'SET-ME-PLEASE',
            'webhook_endpoint_secret': 'SET-ME-PLEASE',
        },
    },
}
# END PAYMENT PROCESSING


# CELERY
BROKER_URL = 'redis://'

# Uncomment this to run tasks in-process (i.e., synchronously).
# CELERY_ALWAYS_EAGER = True
# END CELERY


ENABLE_AUTO_AUTH = True

REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] + ('rest_framework.renderers.BrowsableAPIRenderer',)

#####################################################################
# Lastly, see if the developer has any local overrides.
if os.path.isfile(join(dirname(abspath(__file__)), 'private.py')):
    from .private import *  # pylint: disable=import-error

ENTERPRISE_API_URL = urljoin(f"{ENTERPRISE_SERVICE_URL}/", 'api/v1/')

ENTERPRISE_CATALOG_API_URL = urljoin(f"{ENTERPRISE_CATALOG_SERVICE_URL}/", 'api/v1/')
