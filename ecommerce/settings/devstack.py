"""Devstack settings"""
from os import environ

import yaml

from ecommerce.settings import get_lms_url
from ecommerce.settings.base import *
from ecommerce.settings.logger import get_logger_config

LOGGING = get_logger_config(debug=True, dev_env=True, local_loglevel='DEBUG')

# Pull in base setting overrides from configuration file.
CONFIG_FILE = environ.get('ECOMMERCE_CFG')
if CONFIG_FILE is not None:
    with open(CONFIG_FILE) as f:
        overrides = yaml.load(f)
        vars().update(overrides)

DEBUG = True
ENABLE_AUTO_AUTH = True

# PAYMENT PROCESSING
PAYMENT_PROCESSORS = (
    'ecommerce.extensions.payment.processors.adyen.Adyen',
    'ecommerce.extensions.payment.processors.cybersource.Cybersource',
    'ecommerce.extensions.payment.processors.paypal.Paypal',
)

# PAYMENT PROCESSING
PAYMENT_PROCESSOR_CONFIG = {
    'adyen': {
        'payment_page_url': 'https://test.adyen.com/hpp/select.shtml',
        'skin_code': '69LHboek',
        'merchant_reference': 'SKINTEST-1457382180204',
        'merchant_account': 'EdXORG',
        'secret_key': '5F1C8A4C07575478D32D55729A962C4390C3E5604CA57C72563FB7C3B8EC918F'
    },
    'cybersource': {
        'merchant_id': 'edx_org',
        'transaction_key': 'fake-transaction-key',
        'soap_api_url': 'https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.115.wsdl',
        'profile_id': 'CD358EFA-440E-4C17-B7CA-BD4C581E6BFA',
        'access_key': '13c6588656d93019885bbdd4fcd84026',
        'secret_key': 'd9a31d0b621846fca901a8cc2c57f2a19dbf3edaac3d45c5aed84f2ff58e234af8cd8a5728734355bc044e134cbdd69fbdadfde9ad7b40d2a02b8b586ec917a000b5472b738b495e968298b72d01baa0225b91d28ad14b9a9cc4f829b7d922f79e213d4f0daa49d0b6713e8e0c268cafe79d207301004fa691f0e1a76fdd87bb',
        'payment_page_url': 'https://testsecureacceptance.cybersource.com/pay',
        'receipt_page_url': get_lms_url('/commerce/checkout/receipt/'),
        'cancel_page_url': get_lms_url('/commerce/checkout/cancel/'),
    },
    'paypal': {
        'mode': 'sandbox',
        'client_secret': 'EI_xpyNCsEOzlZ6EsfEVM6oLasYYU3nWj9mLYTiTBAZLq1o5GW727rFn8ATX4JXR9az9_SkEmcr0qrvN',
        'client_id': 'Abqo9vwtAafllqb-5E5GspOhvexGAbwilkvNR6AtjSVu3F0Eo9hFRUCsGfR7QfqP5rX0asynQZb63a_Z',
        'receipt_url': get_lms_url('/commerce/checkout/receipt/'),
        'cancel_url': get_lms_url('/commerce/checkout/cancel/'),
        'error_url': 'aaa'
  },
}
# END PAYMENT PROCESSING
# Load private settings
if os.path.isfile(join(dirname(abspath(__file__)), 'private.py')):
    from .private import *  # pylint: disable=import-error
