# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import pprint

import datetime
import logging
import uuid
from decimal import Decimal

from django.conf import settings
from oscar.apps.payment.exceptions import UserCancelled, GatewayError, TransactionDeclined
from oscar.core.loading import get_model

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.constants import CYBERSOURCE_CARD_TYPE_MAP
from ecommerce.extensions.payment.exceptions import (InvalidSignatureError, InvalidCybersourceDecision,
                                                     PartialAuthorizationError)
from ecommerce.extensions.payment.helpers import sign
from ecommerce.extensions.payment.processors import BasePaymentProcessor
from ecommerce.extensions.payment.transport import RequestsTransport

logger = logging.getLogger(__name__)

PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
ProductClass = get_model('catalogue', 'ProductClass')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')



import binascii
import hashlib
import hmac
from collections import OrderedDict


class PayboxSystem(BasePaymentProcessor):
    """
    CyberSource Secure Acceptance Web/Mobile (February 2015)

    For reference, see
    http://apps.cybersource.com/library/documentation/dev_guides/Secure_Acceptance_WM/Secure_Acceptance_WM.pdf.
    """

    NAME = 'paybox_system'

    def __init__(self):
        """
        Constructs a new instance of the CyberSource processor.

        Raises:
            KeyError: If no settings configured for this payment processor
            AttributeError: If LANGUAGE_CODE setting is not set.
        """
        configuration = self.configuration
        self.PBX_SITE = configuration['PBX_SITE']
        self.PBX_RANG = configuration['PBX_RANG']
        self.PBX_IDENTIFIANT = configuration['PBX_IDENTIFIANT']
        self.PBX_REPONDRE_A = configuration['PBX_REPONDRE_A']
        self.private_key = configuration['private_key']
        self.payment_page_url = configuration['payment_page_url']
        self.receipt_page_url = configuration['receipt_page_url']
        self.cancel_page_url = configuration['cancel_page_url']
        self.language_code = settings.LANGUAGE_CODE

    def get_transaction_parameters(self, basket, request=None):
        """
        Generate a dictionary of signed parameters CyberSource requires to complete a transaction.

        Arguments:
            basket (Basket): The basket of products being purchased.

        Keyword Arguments:
            request (Request): A Request object which could be used to construct an absolute URL; not
                used by this method.

        Returns:
            dict: CyberSource-specific parameters required to complete a transaction, including a signature.
        """
        params = OrderedDict()
        params['PBX_ANNULE'] = self.cancel_page_url
        params['PBX_CMD'] = basket.order_number
        params['PBX_DEVISE'] = '978'   # €EURO
        params['PBX_EFFECTUE'] = self.receipt_page_url  # '{}?order={}'.format(self.receipt_page_url, basket.order_number)
        params['PBX_IDENTIFIANT'] = self.PBX_IDENTIFIANT
        params['PBX_PORTEUR'] = basket.owner.email
        params['PBX_RANG'] = self.PBX_RANG
        params['PBX_REFUSE'] = self.cancel_page_url
        params['PBX_REPONDRE_A'] = self.PBX_REPONDRE_A
        params['PBX_RETOUR'] = 'amount:M;reference-fun:R;autorisation:A;erreur:E;appel-paybox:T;transaction-paybox:S'
        params['PBX_RUF1'] = 'POST'    # Initial form method
        params['PBX_SITE'] = self.PBX_SITE
        params['PBX_TIME'] = self.utcnow().strftime(ISO_8601_FORMAT)
        params['PBX_TOTAL'] = str(int(basket.total_incl_tax * 100))
        params['PBX_TYPECARTE'] = 'CB'    # Force payment mode to CB/VISA
        params['PBX_TYPEPAIEMENT'] = 'CARTE'

        #params['reference_number'] = basket.order_number
        #params['amount'] = str(basket.total_incl_tax)
        #params['currency'] = basket.currency,
        #params['consumer_id'] = basket.owner.username,
        #import ipdb; ipdb.set_trace()
        hmac_query = '&'.join(['%s=%s' % (key, value) for key, value in params.items()])
        binary_key = binascii.unhexlify(self.private_key)
        hmac_hash = hmac.new(binary_key, hmac_query, hashlib.sha512).hexdigest().upper()
        #hmac_query += '&PBX_HMAC=' + hmac_hash

        params['PBX_HMAC'] = hmac_hash
        print params

        params['payment_page_url'] = self.payment_page_url

        # '/payment/fake-payment-page/'
        #import ipdb; ipdb.set_trace()
        return params

    @staticmethod
    def utcnow():
        """
        Returns the current datetime in UTC.

        This is primarily here as a test helper, since we cannot mock datetime.datetime.
        """
        return datetime.datetime.utcnow()


    def handle_processor_response(self, response, basket=None):
        """
        Handle a response (i.e., "merchant notification") from CyberSource.

        This method does the following:
            1. Verify the validity of the response.
            2. Create PaymentEvents and Sources for successful payments.

        Arguments:
            response (dict): Dictionary of parameters received from the payment processor.

        Keyword Arguments:
            basket (Basket): Basket being purchased via the payment processor.

        Raises:
            UserCancelled: Indicates the user cancelled payment.
            TransactionDeclined: Indicates the payment was declined by the processor.
            GatewayError: Indicates a general error on the part of the processor.
            InvalidCyberSourceDecision: Indicates an unknown decision value.
                Known values are ACCEPT, CANCEL, DECLINE, ERROR.
            PartialAuthorizationError: Indicates only a portion of the requested amount was authorized.
        """

        #import ipdb; ipdb.set_trace()
        # Raise an exception for payments that were not accepted. Consuming code should be responsible for handling
        # and logging the exception.
        code = response['erreur']
        if code != '00000':
            exception = {
                'cancel': UserCancelled,   #TODO: implement Paybox error codes
                'decline': TransactionDeclined,
                '00001': GatewayError
            }.get(code, InvalidCybersourceDecision)

            raise exception


        # Create Source to track all transactions related to this processor and order
        source_type, __ = SourceType.objects.get_or_create(name=self.NAME)
        amount = Decimal(response['amount'])
        transaction_id = response['transaction-paybox']

        source = Source(source_type=source_type,
                        currency=settings.OSCAR_DEFAULT_CURRENCY,
                        amount_allocated=amount,
                        amount_debited=amount,
                        reference=transaction_id,
                        )

        # Create PaymentEvent to track
        event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.PAID)
        event = PaymentEvent(event_type=event_type, amount=amount, reference=transaction_id, processor_name=self.NAME)

        return source, event


    def is_signature_valid(self, response):
        """Returns a boolean indicating if the response's signature (indicating potential tampering) is valid."""
        return response and (self._generate_signature(response) == response.get('signature'))

    def issue_credit(self, source, amount, currency):
        order = source.order

        raise


    @classmethod
    def is_enabled(cls):
        return True   # override waffle switch system, as I currently do not understand it

