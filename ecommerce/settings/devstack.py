"""Devstack settings"""
from os import environ

import yaml

from ecommerce.settings.base import *
from ecommerce.settings.logger import get_logger_config


LOGGING = get_logger_config()

# Pull in base setting overrides from configuration file.
CONFIG_FILE = environ.get('ECOMMERCE_CFG')
if CONFIG_FILE is not None:
    with open(CONFIG_FILE) as f:
        overrides = yaml.load(f)
        vars().update(overrides)


# DEBUG CONFIGURATION
DEBUG = True
# END DEBUG CONFIGURATION


# AUTHENTICATION
JWT_AUTH.update({
    # Must match LMS' ECOMMERCE_API_SIGNING_KEY setting
    'JWT_SECRET_KEY': 'insecure-secret-key',
    # Must match LMS' JWT_ISSUER setting
    'JWT_ISSUER': OAUTH2_PROVIDER_URL
})

# Must match LMS' EDX_API_KEY setting
EDX_API_KEY = 'replace-me'

ENABLE_AUTO_AUTH = True
# END AUTHENTICATION


# PAYMENT PROCESSING
PAYMENT_PROCESSOR_CONFIG = {
    'cybersource': {
        'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.115.wsdl',
        'merchant_id': 'fake-merchant-id',
        'transaction_key': 'fake-transaction-key',
        'profile_id': 'fake-profile-id',
        'access_key': 'fake-access-key',
        'secret_key': 'fake-secret-key',
        'payment_page_url': 'https://testsecureacceptance.cybersource.com/pay',
        'receipt_page_url': get_lms_url('/commerce/checkout/receipt/'),
        'cancel_page_url': get_lms_url('/commerce/checkout/cancel/'),
    },
    'paypal': {
        'mode': 'sandbox',
        'client_id': 'fake-client-id',
        'client_secret': 'fake-client-secret',
        'receipt_url': get_lms_url('/commerce/checkout/receipt/'),
        'cancel_url': get_lms_url('/commerce/checkout/cancel/'),
    },
}
# END PAYMENT PROCESSING
