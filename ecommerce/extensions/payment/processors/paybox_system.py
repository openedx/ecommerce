""" PayBoxSystem proto. """
from __future__ import unicode_literals




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


class PayBoxSystem(BasePaymentProcessor):
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
        params['PBX_SITE'] = self.PBX_SITE
        params['PBX_RANG'] = self.PBX_RANG
        params['PBX_IDENTIFIANT'] = self.PBX_IDENTIFIANT
        params['PBX_CMD'] = "FUN" + uuid.uuid4().hex
        params['PBX_PORTEUR'] = 'richard@openfun.fr'  #basket.owner.username
        params['PBX_RETOUR'] = 'Mt:M;Ref:R;Auto:A;Erreur:E'
        params['PBX_TIME'] = self.utcnow().strftime(ISO_8601_FORMAT)
        params['PBX_TYPECARTE'] = 'CB'
        params['PBX_TYPEPAIEMENT'] = 'CARTE'
        params['PBX_DEVISE'] = '978',   # basket.currenc
        params['PBX_TOTAL'] = str(basket.total_incl_tax)
        params['PBX_EFFECTUE'] = '{}?order={}'.format(self.receipt_page_url, basket.order_number)
        params['PBX_REFUSE'] = self.cancel_page_url
        params['PBX_ANNULE'] = self.cancel_page_url
        params['PBX_RUF1'] = 'POST'
        params['reference_number'] = basket.order_number
        params['amount'] = str(basket.total_incl_tax)
        params['currency'] = basket.currency,
        params['consumer_id'] = basket.owner.username,

        hmac_query = '&'.join(['%s=%s' % (key, value) for key, value in params.items()])
        binary_key = binascii.unhexlify(self.private_key)
        hmac_hash = hmac.new(binary_key, hmac_query, hashlib.sha512).hexdigest().upper()
        params['PBX_HMAC'] = hmac_hash

        params['payment_page_url'] = '/payment/fake-payment-page/'  # self.payment_page_url
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
        decision = response['decision'].lower()
        if decision != 'accept':
            exception = {
                'cancel': UserCancelled,
                'decline': TransactionDeclined,
                'error': GatewayError
            }.get(decision, InvalidCybersourceDecision)

            raise exception

        # Raise an exception if the authorized amount differs from the requested amount.
        # Note (CCB): We should never reach this point in production since partial authorization is disabled
        # for our account, and should remain that way until we have a proper solution to allowing users to
        # complete authorization for the entire order.
        if response['auth_amount'] != response['req_amount']:
            raise PartialAuthorizationError

        # Create Source to track all transactions related to this processor and order
        source_type, __ = SourceType.objects.get_or_create(name=self.NAME)
        currency = response['req_currency']
        total = Decimal(response['req_amount'])
        transaction_id = response['transaction_id']
        req_card_number = response['req_card_number']
        card_type = CYBERSOURCE_CARD_TYPE_MAP.get(response['req_card_type'])

        source = Source(source_type=source_type,
                        currency=currency,
                        amount_allocated=total,
                        amount_debited=total,
                        reference=transaction_id,
                        label=req_card_number,
                        card_type=card_type)

        # Create PaymentEvent to track
        event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.PAID)
        event = PaymentEvent(event_type=event_type, amount=total, reference=transaction_id, processor_name=self.NAME)

        return source, event


    def is_signature_valid(self, response):
        """Returns a boolean indicating if the response's signature (indicating potential tampering) is valid."""
        return response and (self._generate_signature(response) == response.get('signature'))

    def issue_credit(self, source, amount, currency):
        order = source.order

        try:
            order_request_token = source.reference

            security = Security()
            token = UsernameToken(self.merchant_id, self.transaction_key)
            security.tokens.append(token)

            client = Client(self.soap_api_url, transport=RequestsTransport())
            client.set_options(wsse=security)

            credit_service = client.factory.create('ns0:CCCreditService')
            credit_service._run = 'true'  # pylint: disable=protected-access
            credit_service.captureRequestID = source.reference

            purchase_totals = client.factory.create('ns0:PurchaseTotals')
            purchase_totals.currency = currency
            purchase_totals.grandTotalAmount = unicode(amount)

            response = client.service.runTransaction(merchantID=self.merchant_id, merchantReferenceCode=order.number,
                                                     orderRequestToken=order_request_token,
                                                     ccCreditService=credit_service,
                                                     purchaseTotals=purchase_totals)
            request_id = response.requestID
            ppr = self.record_processor_response(suds_response_to_dict(response), transaction_id=request_id,
                                                 basket=order.basket)
        except:
            msg = 'An error occurred while attempting to issue a credit (via CyberSource) for order [{}].'.format(
                order.number)
            logger.exception(msg)
            raise GatewayError(msg)

        if response.decision == 'ACCEPT':
            source.refund(amount, reference=request_id)
            event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.REFUNDED)
            PaymentEvent.objects.create(event_type=event_type, order=order, amount=amount, reference=request_id,
                                        processor_name=self.NAME)
        else:
            raise GatewayError(
                'Failed to issue CyberSource credit for order [{order_number}]. '
                'Complete response has been recorded in entry [{response_id}]'.format(
                    order_number=order.number, response_id=ppr.id))

    @classmethod
    def is_enabled(cls):
        return True   # override waffle switch system, as I currently do not understand it

