""" Adyen payment processing. """
import datetime
from decimal import Decimal
import logging
import uuid

import base64
import hmac
import hashlib
import binascii
from collections import OrderedDict

from django.conf import settings
from oscar.apps.payment.exceptions import UserCancelled, GatewayError, TransactionDeclined
from oscar.core.loading import get_model
from suds.client import Client
from suds.sudsobject import asdict
from suds.wsse import Security, UsernameToken

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.constants import CYBERSOURCE_CARD_TYPE_MAP
from ecommerce.extensions.payment.exceptions import (InvalidSignatureError, InvalidCybersourceDecision,
                                                     PartialAuthorizationError)
from ecommerce.extensions.payment.helpers import sign
from ecommerce.extensions.payment.processors import BasePaymentProcessor


logger = logging.getLogger(__name__)

PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
ProductClass = get_model('catalogue', 'ProductClass')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class Adyen(BasePaymentProcessor):
    """
    Adyen Secure Acceptance Web/Mobile (February 2015)
    """

    NAME = 'adyen'

    def __init__(self):
        """
        Constructs a new instance of the Adyen processor.

        Raises:
            KeyError: If no settings configured for this payment processor
            AttributeError: If LANGUAGE_CODE setting is not set.
        """
        configuration = self.configuration
        self.payment_page_url = configuration.get("payment_page_url")
        self.skin_code = configuration.get("skin_code")
        self.merchant_reference = configuration.get("merchant_reference")
        self.merchant_account = configuration.get("merchant_account")
        self.secret_key = configuration.get('secret_key')
        self.language_code = settings.LANGUAGE_CODE

    def get_transaction_parameters(self, basket, request=None):
        """
        Generate a dictionary of signed parameters Adyen requires to complete a transaction.
        """
        parameters = {
            'skinCode': self.skin_code,
            'currencyCode': basket.currency,
            'paymentAmount': str(int(basket.total_incl_tax * 100)),
            'merchantReference': self.merchant_reference,
            'merchantAccount': self.merchant_account,
            'sessionValidity': self.utcnow().strftime(ISO_8601_FORMAT),
            'shipBeforeDate': self.utcnow().strftime(ISO_8601_FORMAT),
            'shopperLocale': self.language_code
        }

        parameters.update({
            'merchantSig': self._generate_signature(parameters),
            'payment_page_url': self.payment_page_url
        })
        return parameters

    @staticmethod
    def utcnow():
        """
        Returns the current datetime in UTC.

        This is primarily here as a test helper, since we cannot mock datetime.datetime.
        """
        return datetime.datetime.utcnow() + datetime.timedelta(1)

    def _generate_signature(self, parameters):
        parameters = OrderedDict(sorted(parameters.items(), key=lambda t: t[0]))
        signing_string = ':'.join(map(self.escape_value, parameters.keys() + parameters.values()))
        hm = hmac.new(binascii.a2b_hex(self.secret_key), signing_string, hashlib.sha256)
        return base64.b64encode(hm.digest())

    @staticmethod
    def escape_value(val):
        return val.replace('\\', '\\\\').replace(':', '\\:')

    def handle_processor_response(self, response, basket=None):
        """
        Handle a response (i.e., "merchant notification") from Adyen.
        """
        pass

    def issue_credit(self, source, amount, currency):
        pass

