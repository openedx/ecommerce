# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import binascii
from collections import OrderedDict
import datetime
from decimal import Decimal
import hashlib
import hmac
import logging


from django.conf import settings
from oscar.apps.payment.exceptions import UserCancelled, TransactionDeclined
from oscar.core.loading import get_model

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.processors import BasePaymentProcessor

logger = logging.getLogger(__name__)

PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class PayboxSystem(BasePaymentProcessor):
    """
    Paybox
    """

    NAME = 'paybox_system'

    def __init__(self):
        """
        Constructs a new instance of the Paybox processor.
        """

        configuration = self.configuration
        self.PBX_SITE = configuration['PBX_SITE']
        self.PBX_RANG = configuration['PBX_RANG']
        self.PBX_IDENTIFIANT = configuration['PBX_IDENTIFIANT']
        self.PBX_REPONDRE_A = configuration['PBX_REPONDRE_A']
        self.private_key = configuration['private_key']
        self.payment_page_url = configuration['payment_page_url']
        self.receipt_page_url = configuration['receipt_page_url']
        self.error_page_url = configuration['error_page_url']
        self.cancel_page_url = configuration['cancel_page_url']
        self.language_code = settings.LANGUAGE_CODE

    def get_transaction_parameters(self, basket, request=None):
        """
        Generate a dictionary of signed parameters Paybox requires to complete a transaction.

        Arguments:
            basket (Basket): The basket of products being purchased.

        Returns:
            dict: Paybox-specific parameters required to complete a transaction, including a signature.
        """
        params = OrderedDict()
        params['PBX_ANNULE'] = self.cancel_page_url
        params['PBX_CMD'] = basket.order_number
        params['PBX_DEVISE'] = '978'   # €EURO
        params['PBX_EFFECTUE'] = self.receipt_page_url
        params['PBX_IDENTIFIANT'] = self.PBX_IDENTIFIANT
        params['PBX_PORTEUR'] = basket.owner.email
        params['PBX_RANG'] = self.PBX_RANG
        params['PBX_REFUSE'] = self.error_page_url
        params['PBX_ANNULE'] = self.cancel_page_url
        params['PBX_REPONDRE_A'] = self.PBX_REPONDRE_A
        params['PBX_RETOUR'] = 'amount:M;reference-fun:R;autorisation:A;reponse-paybox:E;appel-paybox:T;transaction-paybox:S'
        params['PBX_RUF1'] = 'POST'    # Initial form method
        params['PBX_SITE'] = self.PBX_SITE
        params['PBX_TIME'] = self.utcnow().strftime(ISO_8601_FORMAT)
        params['PBX_TOTAL'] = str(int(basket.total_incl_tax * 100))
        params['PBX_TYPECARTE'] = 'CB'    # Force payment mode to CB/VISA
        params['PBX_TYPEPAIEMENT'] = 'CARTE'

        # Sign request sent to Paybox
        # As the signature is made regarding fields order, this order has to be maintained
        # in other steps of the process. See edx-platform/lms/djangoapps/verify_student/views.py:192 (6cb90df)
        hmac_query = '&'.join(['%s=%s' % (key, value) for key, value in params.items()])
        binary_key = binascii.unhexlify(self.private_key)
        hmac_hash = hmac.new(binary_key, hmac_query, hashlib.sha512).hexdigest().upper()

        params['PBX_HMAC'] = hmac_hash
        params['payment_page_url'] = self.payment_page_url

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
        Handle a response (i.e., "merchant notification") from Paybox.

        This method does the following:
            1. Create PaymentEvents and Sources for successful payments.

        Arguments:
            response (dict): Dictionary of parameters received from the payment processor.

        Keyword Arguments:
            basket (Basket): Basket being purchased via the payment processor.

        Raises:
            UserCancelled: Indicates the user cancelled payment.
            TransactionDeclined: Indicates the payment was declined by the processor.
        """

        # Raise an exception for payments that were not accepted. Consuming code should be responsible for handling
        # and logging the exception.
        code = response['reponse-paybox']
        if code != '00000':
            if code == '00001':
                raise UserCancelled
            else:
                raise TransactionDeclined

        # Create Source to track all transactions related to this processor and order
        source_type, __ = SourceType.objects.get_or_create(name=self.NAME)
        amount = Decimal(response['amount']) / 100  # Paybox work in cents as Oscar stores Decimals
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

    def issue_credit(self, source, amount, currency):
        """This method is call by Oscar backoffice when a user requested reimbursement and we accept it.
        As 'Paybox system' do no allow reimbursemement, it have to be done manualy in Paybox's backoffice.
        See: http://localhost:8080/dashboard/refunds/
        """
        return

    @classmethod
    def is_enabled(cls):
        return True   # override waffle switch system, as I currently do not understand it
