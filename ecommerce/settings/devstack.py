"""Devstack settings"""
from ecommerce.settings.production import *

DEBUG = True
ENABLE_AUTO_AUTH = True
PROTOCOL = 'http'

# Docker does not support the syslog socket at /dev/log. Rely on the console.
LOGGING['handlers']['local'] = {
    'class': 'logging.NullHandler',
}

# Determine which requests should render Django Debug Toolbar
INTERNAL_IPS = ('127.0.0.1',)

SOCIAL_AUTH_REDIRECT_IS_HTTPS = False

# TODO Remove this once we convert the E-Commerce service to use the latest JWT_ISSUERS configuration.
JWT_AUTH['JWT_DECODE_HANDLER'] = 'edx_rest_framework_extensions.utils.jwt_decode_handler'

# Allow live changes to JS and CSS
COMPRESS_OFFLINE = False
COMPRESS_ENABLED = False

# PAYMENT PROCESSING
PAYMENT_PROCESSOR_CONFIG = {
    'edx': {
        'cybersource': {
            'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.115.wsdl',
            'merchant_id': 'fake-merchant-id',
            'transaction_key': 'fake-transaction-key',
            'profile_id': 'fake-profile-id',
            'access_key': 'fake-access-key',
            'secret_key': 'fake-secret-key',
            'payment_page_url': 'https://testsecureacceptance.cybersource.com/pay',
            'receipt_path': PAYMENT_PROCESSOR_RECEIPT_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'send_level_2_3_details': True,
        },
        'paypal': {
            'mode': 'sandbox',
            'client_id': 'fake-client-id',
            'client_secret': 'fake-client-secret',
            'receipt_path': PAYMENT_PROCESSOR_RECEIPT_PATH,
            'cancel_checkout_path': PAYMENT_PROCESSOR_CANCEL_PATH,
            'error_path': PAYMENT_PROCESSOR_ERROR_PATH,
        },
    },
}
# END PAYMENT PROCESSING

#####################################################################
# Lastly, see if the developer has any local overrides.
if os.path.isfile(join(dirname(abspath(__file__)), 'private.py')):
    from .private import *  # pylint: disable=import-error
