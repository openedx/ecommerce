"""Payment processing classes containing logic specific to particular payment processors."""
import abc
import datetime
from decimal import Decimal
import logging
import uuid

from django.conf import settings
from oscar.apps.payment.exceptions import UserCancelled, GatewayError, TransactionDeclined
from oscar.core.loading import get_model

from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.constants import ISO_8601_FORMAT, CYBERSOURCE_CARD_TYPE_MAP
from ecommerce.extensions.payment.exceptions import (InvalidSignatureError, InvalidCybersourceDecision,
                                                     PartialAuthorizationError)
from ecommerce.extensions.payment.helpers import sign


logger = logging.getLogger(__name__)

PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
ProductClass = get_model('catalogue', 'ProductClass')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class BasePaymentProcessor(object):  # pragma: no cover
    """Base payment processor class."""
    __metaclass__ = abc.ABCMeta

    NAME = None

    @abc.abstractmethod
    def get_transaction_parameters(self, basket):
        """
        Generate a dictionary of signed parameters required for this processor to complete a transaction.

        Arguments:
            basket (Basket): The basket of products being purchased.

        Returns:
            dict: Payment processor-specific parameters required to complete a transaction.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def handle_processor_response(self, response, basket=None):
        """
        Handle a response from the payment processor.

        This method does the following:
            1. Verify the validity of the response.
            2. Create PaymentEvents and Sources for successful payments.

        Arguments:
            response (dict): Dictionary of parameters received from the payment processor

        Keyword Arguments:
            basket (Basket): Basket whose contents have been purchased via the payment processor
        """
        raise NotImplementedError

    @abc.abstractmethod
    def is_signature_valid(self, response):
        """ Returns a boolean indicating if the response's signature (indicating potential tampering) is valid. """
        raise NotImplementedError

    @property
    def configuration(self):
        """
        Returns the configuration (set in Django settings) specific to this payment processor.

        Returns:
            dict: Payment processor configuration

        Raises:
            KeyError: If no settings found for this payment processor
        """
        return settings.PAYMENT_PROCESSOR_CONFIG[self.NAME]

    def record_processor_response(self, response, transaction_id=None, basket=None):
        """
        Save the processor's response to the database for auditing.

        Arguments:
            response (dict): Response received from the payment processor

        Keyword Arguments:
            transaction_id (string): Identifier for the transaction on the payment processor's servers
            basket (Basket): Basket associated with the payment event (e.g., being purchased)

        Return
            PaymentProcessorResponse
        """
        return PaymentProcessorResponse.objects.create(processor_name=self.NAME, transaction_id=transaction_id,
                                                       response=response, basket=basket)


class Cybersource(BasePaymentProcessor):
    """CyberSource Secure Acceptance Web/Mobile (February 2015)

    For reference, see
    http://apps.cybersource.com/library/documentation/dev_guides/Secure_Acceptance_WM/Secure_Acceptance_WM.pdf.
    """
    NAME = u'cybersource'

    def __init__(self):
        """
        Constructs a new instance of the CyberSource processor.

        Raises:
            KeyError: If no settings configured for this payment processor
            AttributeError: If LANGUAGE_CODE setting is not set.
        """
        configuration = self.configuration
        self.profile_id = configuration['profile_id']
        self.access_key = configuration['access_key']
        self.secret_key = configuration['secret_key']
        self.payment_page_url = configuration['payment_page_url']
        self.receipt_page_url = configuration['receipt_page_url']
        self.cancel_page_url = configuration['cancel_page_url']
        self.language_code = settings.LANGUAGE_CODE

    def get_transaction_parameters(self, basket):
        """
        Generate a dictionary of signed parameters CyberSource requires to complete a transaction.

        Arguments:
            basket (Basket): The basket of products being purchased.

        Returns:
            dict: CyberSource-specific parameters required to complete a transaction, including a signature.
        """
        parameters = {
            u'access_key': self.access_key,
            u'profile_id': self.profile_id,
            u'transaction_uuid': uuid.uuid4().hex,
            u'signed_field_names': u'',
            u'unsigned_field_names': u'',
            u'signed_date_time': datetime.datetime.utcnow().strftime(ISO_8601_FORMAT),
            u'locale': self.language_code,
            u'transaction_type': u'sale',
            u'reference_number': unicode(basket.id),
            u'amount': unicode(basket.total_incl_tax),
            u'currency': basket.currency,
            u'consumer_id': basket.owner.username,
            u'override_custom_receipt_page': u'{}?basket_id={}'.format(self.receipt_page_url, basket.id),
            u'override_custom_cancel_page': self.cancel_page_url,
        }

        # XCOM-274: when internal reporting across all processors is
        # operational, these custom fields will no longer be needed and should
        # be removed.
        single_seat = self.get_single_seat(basket)
        if single_seat:
            parameters[u'merchant_defined_data1'] = single_seat.attr.course_key
            parameters[u'merchant_defined_data2'] = single_seat.attr.certificate_type

        # Sign all fields
        signed_field_names = parameters.keys()
        parameters[u'signed_field_names'] = u','.join(sorted(signed_field_names))
        parameters[u'signature'] = self._generate_signature(parameters)

        return parameters

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
        line = basket.lines.filter(product__product_class=seat_class).first()
        return line.product if line else None

    def handle_processor_response(self, response, basket=None):
        """
        Handle a response from the payment processor.

        This method does the following:
            1. Verify the validity of the response.
            2. Create PaymentEvents and Sources for successful payments.

        Args:
            response (dict): Dictionary of parameters received from the payment processor.
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
        decision = response[u'decision'].lower()
        if decision != u'accept':
            exception = {
                u'cancel': UserCancelled,
                u'decline': TransactionDeclined,
                u'error': GatewayError
            }.get(decision, InvalidCybersourceDecision)

            raise exception

        # Raise an exception if the authorized amount differs from the requested amount.
        # Note (CCB): We should never reach this point in production since partial authorization is disabled
        # for our account, and should remain that way until we have a proper solution to allowing users to
        # complete authorization for the entire order.
        if response[u'auth_amount'] != response[u'req_amount']:
            raise PartialAuthorizationError

        # Create Source to track all transactions related to this processor and order
        source_type, __ = SourceType.objects.get_or_create(name=self.NAME)
        currency = response[u'req_currency']
        total = Decimal(response[u'req_amount'])
        transaction_id = response[u'transaction_id']
        req_card_number = response[u'req_card_number']
        card_type = CYBERSOURCE_CARD_TYPE_MAP.get(response[u'req_card_type'])

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
        """Sign the contents of the provided transaction parameters dictionary.

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
        keys = parameters[u'signed_field_names'].split(u',')
        # Generate a comma-separated list of keys and values to be signed. CyberSource refers to this
        # as a 'Version 1' signature in their documentation.
        message = u','.join([u'{key}={value}'.format(key=key, value=parameters.get(key)) for key in keys])

        return sign(message, self.secret_key)

    def is_signature_valid(self, response):
        return response and (self._generate_signature(response) == response.get(u'signature'))
