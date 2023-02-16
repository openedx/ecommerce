

from urllib.parse import urljoin

from path import Path

from ecommerce.settings.base import *

SITE_ID = 1
PROTOCOL = 'http'
ALLOWED_HOSTS = ['*']

# Disable syslog logging since we usually do not have syslog enabled in test environments.
LOGGING['handlers']['local'] = {'class': 'logging.NullHandler'}

# Disable console logging to cut down on log size. Nose will capture the logs for us.
LOGGING['handlers']['console'] = {'class': 'logging.NullHandler'}

# END TEST SETTINGS

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.environ.get('DB_NAME', ':memory:'),
        'USER': os.environ.get('DB_USER', ''),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', ''),
        'PORT': os.environ.get('DB_PORT', ''),
        'CONN_MAX_AGE': int(os.environ.get('CONN_MAX_AGE', 0)),
        'ATOMIC_REQUESTS': True,
    },
}

# AUTHENTICATION
ENABLE_AUTO_AUTH = True

JWT_AUTH.update({
    'JWT_SECRET_KEY': 'test-secret-key',
    'JWT_ISSUERS': [{
        'SECRET_KEY': 'test-secret-key',
        'AUDIENCE': 'test-audience',
        'ISSUER': 'test-issuer'
    }],
})

PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
)
# END AUTHENTICATION


# ORDER PROCESSING
EDX_API_KEY = 'replace-me'
# END ORDER PROCESSING


# PAYMENT PROCESSING
PAYMENT_PROCESSOR_CONFIG = {
    'edx': {
        'cybersource': {
            'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.166.wsdl',
            'merchant_id': 'fake-merchant-id',
            'transaction_key': 'fake-transaction-key',
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'send_level_2_3_details': True,
            'apple_pay_merchant_identifier': 'merchant.com.example',
            'apple_pay_merchant_id_domain_association': 'fake-merchant-id-domain-association',
            'apple_pay_merchant_id_certificate_path': '',
            'apple_pay_country_code': 'US',
        },
        'cybersource-rest': {
            'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.166.wsdl',
            'merchant_id': 'fake-merchant-id',
            'transaction_key': 'fake-transaction-key',
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'send_level_2_3_details': True,
            'apple_pay_merchant_identifier': 'merchant.com.example',
            'apple_pay_merchant_id_domain_association': 'fake-merchant-id-domain-association',
            'apple_pay_merchant_id_certificate_path': '',
            'apple_pay_country_code': 'US',
            'flex_shared_secret_key_id': 'd2df1f49-dffa-4814-8da2-2751a62b79a6',
            'flex_shared_secret_key': 'c9QEORcKDT7u27zLtuy2S0T/HfKo8gl+JnCy6OHtm9Q=',
        },
        'paypal': {
            'mode': 'sandbox',
            'client_id': 'fake-client-id',
            'client_secret': 'fake-client-secret',
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'error_path': PAYMENT_PROCESSOR_ERROR_PATH,
        },
        'invoice': {},
        'stripe': {
            'api_version': '2022-08-01; server_side_confirmation_beta=v1',
            'enable_telemetry': None,
            'log_level': 'debug',
            'max_network_retries': 0,
            'proxy': None,
            'publishable_key': 'fake-publishable-key',
            'secret_key': 'fake-secret-key',
            'webhook_endpoint_secret': 'fake-webhook-key',
            'error_path': PAYMENT_PROCESSOR_ERROR_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'receipt_url': PAYMENT_PROCESSOR_RECEIPT_PATH,
        },
        'android-iap': {
            'google_bundle_id': '<put-value-here>',
            'google_service_account_key_file': '<put-value-here>'
        },
        'ios-iap': {
            'ios_bundle_id': '<put-value-here>',
        }
    },
    'other': {
        'cybersource': {
            'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.166.wsdl',
            'merchant_id': 'other-fake-merchant-id',
            'transaction_key': 'other-fake-transaction-key',
            'receipt_path': PAYMENT_PROCESSOR_RECEIPT_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'send_level_2_3_details': True,
        },
        'cybersource-rest': {
            'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.166.wsdl',
            'merchant_id': 'other-fake-merchant-id',
            'transaction_key': 'other-fake-transaction-key',
            'receipt_path': PAYMENT_PROCESSOR_RECEIPT_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'send_level_2_3_details': True,
        },
        'paypal': {
            'mode': 'sandbox',
            'client_id': 'other-fake-client-id',
            'client_secret': 'other-fake-client-secret',
            'receipt_path': PAYMENT_PROCESSOR_RECEIPT_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'error_path': PAYMENT_PROCESSOR_ERROR_PATH,
        },
        'invoice': {},
        'stripe': {
            'api_version': '2022-08-01; server_side_confirmation_beta=v1',
            'enable_telemetry': None,
            'log_level': 'debug',
            'max_network_retries': 0,
            'proxy': None,
            'publishable_key': 'fake-publishable-key',
            'secret_key': 'fake-secret-key',
            'webhook_endpoint_secret': 'fake-webhook-key',
            'error_path': PAYMENT_PROCESSOR_ERROR_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'receipt_url': PAYMENT_PROCESSOR_RECEIPT_PATH,
        },
        'android-iap': {
            'google_bundle_id': 'org.edx.mobile',
            'google_service_account_key_file': '<put-value-here>'
        },
        'ios-iap': {
            'ios_bundle_id': 'org.edx.mobile',
        }
    }
}

# END PAYMENT PROCESSING


# CELERY
# Run tasks in-process, without sending them to the queue (i.e., synchronously).
CELERY_ALWAYS_EAGER = True
# END CELERY


# Use production settings for asset compression so that asset compilation can be tested on the CI server.
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

# Comprehensive theme settings for testing environment
COMPREHENSIVE_THEME_DIRS = [
    Path(DJANGO_ROOT + "/tests/themes"),
    Path(DJANGO_ROOT + "/tests/themes-dir-2"),
]

DEFAULT_SITE_THEME = "test-theme"

ENTERPRISE_API_URL = urljoin(f"{ENTERPRISE_SERVICE_URL}/", 'api/v1/')

ENTERPRISE_CATALOG_API_URL = urljoin(f"{ENTERPRISE_CATALOG_SERVICE_URL}/", 'api/v1/')

# Don't bother sending fake events to Segment. Doing so creates unnecessary threads.
SEND_SEGMENT_EVENTS = False

# SPEED
DEBUG = False
TEMPLATE_DEBUG = False
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
BROKER_BACKEND = 'memory'

# Awin advertiser id
AWIN_ADVERTISER_ID = 1234

ENABLE_EXECUTIVE_EDUCATION_2U_FULFILLMENT = True
