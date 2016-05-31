""" CyberSource payment processing. """
from __future__ import unicode_literals

import datetime
import logging
import uuid
from decimal import Decimal

from django.conf import settings
from oscar.apps.payment.exceptions import UserCancelled, GatewayError, TransactionDeclined
from oscar.core.loading import get_model
from suds.client import Client
from suds.sudsobject import asdict
from suds.wsse import Security, UsernameToken
from threadlocals.threadlocals import get_current_request

from ecommerce.core.url_utils import get_lms_url
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


class Cybersource(BasePaymentProcessor):
    """
    CyberSource Secure Acceptance Web/Mobile (February 2015)

    For reference, see
    http://apps.cybersource.com/library/documentation/dev_guides/Secure_Acceptance_WM/Secure_Acceptance_WM.pdf.
    """

    NAME = 'cybersource'

    def __init__(self):
        """
        Constructs a new instance of the CyberSource processor.

        Raises:
            KeyError: If no settings configured for this payment processor
            AttributeError: If LANGUAGE_CODE setting is not set.
        """
        configuration = self.configuration
        self.soap_api_url = configuration['soap_api_url']
        self.merchant_id = configuration['merchant_id']
        self.transaction_key = configuration['transaction_key']
        self.profile_id = configuration['profile_id']
        self.access_key = configuration['access_key']
        self.secret_key = configuration['secret_key']
        self.payment_page_url = configuration['payment_page_url']
        self.send_level_2_3_details = configuration.get('send_level_2_3_details', True)
        self.language_code = settings.LANGUAGE_CODE

    @property
    def receipt_page_url(self):
        return get_lms_url(self.configuration['receipt_path'])

    @property
    def cancel_page_url(self):
        return get_lms_url(self.configuration['cancel_path'])

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
        parameters = {
            'access_key': self.access_key,
            'profile_id': self.profile_id,
            'transaction_uuid': uuid.uuid4().hex,
            'signed_field_names': '',
            'unsigned_field_names': '',
            'signed_date_time': self.utcnow().strftime(ISO_8601_FORMAT),
            'locale': self.language_code,
            'transaction_type': 'sale',
            'reference_number': basket.order_number,
            'amount': str(basket.total_incl_tax),
            'currency': basket.currency,
            'consumer_id': basket.owner.username,
            'override_custom_receipt_page': '{}?orderNum={}'.format(self.receipt_page_url, basket.order_number),
            'override_custom_cancel_page': self.cancel_page_url,
        }

        # XCOM-274: when internal reporting across all processors is
        # operational, these custom fields will no longer be needed and should
        # be removed.
        single_seat = self.get_single_seat(basket)
        if single_seat:
            parameters['merchant_defined_data1'] = single_seat.attr.course_key
            parameters['merchant_defined_data2'] = getattr(single_seat.attr, 'certificate_type', '')

        # Level 2/3 details
        if self.send_level_2_3_details:
            parameters['amex_data_taa1'] = '{}'.format(get_current_request().site.name)
            parameters['purchasing_level'] = '3'
            parameters['line_item_count'] = basket.lines.count()
            # Note (CCB): This field (purchase order) is required for Visa;
            # but, is not actually used by us/exposed on the order form.
            parameters['user_po'] = 'BLANK'

            for index, line in enumerate(basket.lines.all()):
                parameters['item_{}_code'.format(index)] = line.product.get_product_class().slug
                parameters['item_{}_discount_amount '.format(index)] = str(line.discount_value)
                # Note (CCB): This indicates that the total_amount field below includes tax.
                parameters['item_{}_gross_net_indicator'.format(index)] = 'Y'
                parameters['item_{}_name'.format(index)] = line.product.title
                parameters['item_{}_quantity'.format(index)] = line.quantity
                parameters['item_{}_sku'.format(index)] = line.stockrecord.partner_sku
                parameters['item_{}_tax_amount'.format(index)] = str(line.line_tax)
                parameters['item_{}_tax_rate'.format(index)] = '0'
                parameters['item_{}_total_amount '.format(index)] = str(line.line_price_incl_tax_incl_discounts)
                # Note (CCB): Course seat is not a unit of measure. Use item (ITM).
                parameters['item_{}_unit_of_measure'.format(index)] = 'ITM'
                parameters['item_{}_unit_price'.format(index)] = str(line.unit_price_incl_tax)

        # Sign all fields
        signed_field_names = parameters.keys()
        parameters['signed_field_names'] = ','.join(sorted(signed_field_names))
        parameters['signature'] = self._generate_signature(parameters)

        parameters['payment_page_url'] = self.payment_page_url

        return parameters

    @staticmethod
    def utcnow():
        """
        Returns the current datetime in UTC.

        This is primarily here as a test helper, since we cannot mock datetime.datetime.
        """
        return datetime.datetime.utcnow()

    @staticmethod
    def get_single_seat(basket):
        """
        Return the first product encountered in the basket with the product
        class of 'seat'.  Return None if no such products were found.
        """
        try:
            seat_class = ProductClass.objects.get(slug='seat')
        except ProductClass.DoesNotExist:
            # this occurs in test configurations where the seat product class is not in use
            return None

        for line in basket.lines.all():
            product = line.product
            if product.get_product_class() == seat_class:
                return product

        return None

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

        # Validate the signature
        if not self.is_signature_valid(response):
            raise InvalidSignatureError

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

    def _generate_signature(self, parameters):
        """
        Sign the contents of the provided transaction parameters dictionary.

        This allows CyberSource to verify that the transaction parameters have not been tampered with
        during transit. The parameters dictionary should contain a key 'signed_field_names' which CyberSource
        uses to validate the signature. The message to be signed must contain parameter keys and values ordered
        in the same way they appear in 'signed_field_names'.

        We also use this signature to verify that the signature we get back from Cybersource is valid for
        the parameters that they are giving to us.

        Arguments:
            parameters (dict): A dictionary of transaction parameters.

        Returns:
            unicode: the signature for the given parameters
        """
        keys = parameters['signed_field_names'].split(',')
        # Generate a comma-separated list of keys and values to be signed. CyberSource refers to this
        # as a 'Version 1' signature in their documentation.
        message = ','.join(['{key}={value}'.format(key=key, value=parameters.get(key)) for key in keys])

        return sign(message, self.secret_key)

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

        return True


def suds_response_to_dict(d):  # pragma: no cover
    """
    Convert Suds object into serializable format.

    Source: http://stackoverflow.com/a/15678861/592820
    """
    out = {}
    for k, v in asdict(d).iteritems():
        if hasattr(v, '__keylist__'):
            out[k] = suds_response_to_dict(v)
        elif isinstance(v, list):
            out[k] = []
            for item in v:
                if hasattr(item, '__keylist__'):
                    out[k].append(suds_response_to_dict(item))
                else:
                    out[k].append(item)
        else:
            out[k] = v
    return out
