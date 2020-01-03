"""Devstack settings"""
from os import environ

import yaml

from ecommerce.settings import get_lms_url
from ecommerce.settings.base import *
from ecommerce.settings.logger import get_logger_config

LOGGING = get_logger_config(debug=True, dev_env=True, local_loglevel="DEBUG")

# PAYMENT PROCESSING
PAYMENT_PROCESSOR_CONFIG = {
    "cybersource": {
        "soap_api_url": "https://ics2wstest.ic3.com/commerce/1.x/transactionProcessor/CyberSourceTransaction_1.115.wsdl",
        "merchant_id": "fake-merchant-id",
        "transaction_key": "fake-transaction-key",
        "profile_id": "fake-profile-id",
        "access_key": "fake-access-key",
        "secret_key": "fake-secret-key",
        "payment_page_url": "https://testsecureacceptance.cybersource.com/pay",
        "receipt_page_url": get_lms_url("/commerce/checkout/receipt/"),
        "cancel_page_url": get_lms_url("/commerce/checkout/cancel/"),
    },
    "paypal": {
        "mode": "sandbox",
        "client_id": "fake-client-id",
        "client_secret": "fake-client-secret",
        "receipt_url": get_lms_url("/commerce/checkout/receipt/"),
        "cancel_url": get_lms_url("/commerce/checkout/cancel/"),
        "error_url": get_lms_url("/commerce/checkout/error/"),
    },
}
# END OF PAYMENT PROCESSING

# Pull in base setting overrides from configuration file.
CONFIG_FILE = environ.get("ECOMMERCE_CFG")
if CONFIG_FILE is not None:
    with open(CONFIG_FILE) as f:
        overrides = yaml.load(f)
        vars().update(overrides)

DEBUG = True
ENABLE_AUTO_AUTH = True

# Load private settings
if os.path.isfile(join(dirname(abspath(__file__)), "private.py")):
    from .private import *  # pylint: disable=import-error
