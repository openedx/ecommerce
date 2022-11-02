import logging

from oscar.apps.payment.exceptions import GatewayError, PaymentError
from urllib.parse import urljoin
import waffle

from django.db.models import Q
from django.urls import reverse

from ecommerce.extensions.iap.models import IAPProcessorConfiguration
from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.iap.models import PaymentProcessorResponseExtension
from ecommerce.extensions.payment.processors import BasePaymentProcessor, HandledProcessorResponse
from ecommerce.extensions.payment.models import PaymentProcessorResponse
from ecommerce.extensions.payment.exceptions import RedundantPaymentNotificationError


logger = logging.getLogger(__name__)


class BaseIAP(BasePaymentProcessor):
    """
    Base IAP payment processor.
    """
    NAME = None
    TITLE = None
    DEFAULT_PROFILE_NAME = 'default'

    def __init__(self, site):
        """
        Constructs a new instance of the base IAP processor.

        Raises:
            KeyError: If a required setting is not configured for this payment processor
        """
        super(BaseIAP, self).__init__(site)
        self.retry_attempts = IAPProcessorConfiguration.get_solo().retry_attempts
        self.validator = self.get_validator()

    def get_validator(self):
        raise NotImplementedError

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        """
        Generate a dictionary of IAP execution view api endpoint that is required to complete a transaction.

        Arguments:
            basket (Basket): The basket of products being purchased.
            request (Request, optional): A Request object which could be used to construct an
                absolute URL; not used by this method.
            use_client_side_checkout (bool, optional): Indicates if the Silent Order POST
                profile should be used.
            **kwargs: Additional parameters.

        Returns:
            dict: IAP specific parameters required to complete a transaction.
        """
        return {'payment_page_url': urljoin(get_ecommerce_url(), reverse('iap:iap-execute')) }

    def handle_processor_response(self, response, basket=None):
        """
        Execute an approved IAP payment.

        This method creates PaymentEvents and Sources for approved payments.

        Keyword Arguments:
            basket (Basket): Basket being purchased via the payment processor.

        Raises:
            GatewayError: Indicates a general error or unexpected behavior on the part of IAP
                system which prevented an approved payment from being executed.
            PaymentError: Indicates a general error in processing payment details
            RedundantPaymentNotificationError: Indicates that a similar payment was
                initialized before from a different account.

        Returns:
            HandledProcessorResponse
        """
        available_attempts = 1
        product_id = response.get('productId')

        if waffle.switch_is_active('IAP_RETRY_ATTEMPTS'):
            available_attempts = available_attempts + self.retry_attempts

        for attempt_count in range(1, available_attempts + 1):
            validation_response = self.validator.validate(response, self.configuration)
            validation_error = validation_response.get('error')
            if not validation_error:
                break

            entry = self.record_processor_response(validation_error, basket=basket)

            logger.warning(
                "Failed to execute [%s] payment for [%s] on attempt [%d]. "
                "[%s]'s response was recorded in entry [%d].",
                self.NAME,
                product_id,
                attempt_count,
                self.NAME,
                entry.id,
            )

            # After utilizing all retry attempts, raise the exception 'GatewayError'
            if attempt_count == available_attempts:
                logger.error(
                    "Failed to execute [%s] payment for [%s]. "
                    "[%s] response was recorded in entry [%d].",
                    self.NAME,
                    product_id,
                    self.NAME,
                    entry.id
                )
                raise GatewayError(validation_response)

        transaction_id = response.get('transactionId', self._get_transaction_id_from_receipt(validation_response))
        # original_transaction_id is primary identifier for a purchase on iOS
        original_transaction_id = response.get('originalTransactionId', self._get_attribute_from_receipt(
            validation_response, 'original_transaction_id'))

        if self.NAME == 'ios-iap':
            if not original_transaction_id:
                raise PaymentError(response)
            # Check for multiple edx users using same iOS device/iOS account for purchase
            is_redundant_payment = self._is_payment_redundant(basket.owner, original_transaction_id)
            if is_redundant_payment:
                raise RedundantPaymentNotificationError(response)

        self.record_processor_response(
            validation_response,
            transaction_id=transaction_id,
            basket=basket,
            original_transaction_id=original_transaction_id
        )
        logger.info("Successfully executed [%s] payment [%s] for basket [%d].", self.NAME, product_id, basket.id)

        currency = basket.currency
        total = basket.total_incl_tax
        email = basket.owner.email
        label = '{} ({})'.format(self.NAME, email) if email else '{} Account'.format(self.NAME)

        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number=label,
            card_type=None
        )

    def record_processor_response(self, response, transaction_id=None, basket=None, original_transaction_id=None):  # pylint: disable=arguments-differ
        """
        Save the processor's response to the database for auditing.

        Arguments:
            response (dict): Response received from the payment processor

        Keyword Arguments:
            transaction_id (string): Identifier for the transaction on the payment processor's servers
            original_transaction_id (string): Identifier for the transaction for purchase action only
            basket (Basket): Basket associated with the payment event (e.g., being purchased)

        Return
            PaymentProcessorResponse
        """
        processor_response = super(BaseIAP, self).record_processor_response(response, transaction_id=transaction_id,
                                                                            basket=basket)
        if original_transaction_id:
            PaymentProcessorResponseExtension.objects.create(processor_response=processor_response,
                                                             original_transaction_id=original_transaction_id)
        return processor_response

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        raise NotImplementedError('The {} payment processor does not support credit issuance.'.format(self.NAME))

    def _get_attribute_from_receipt(self, validated_receipt, attribute):
        if self.NAME == 'ios-iap':
            return validated_receipt.get('receipt', {}).get('in_app', [{}])[0].get(attribute)
        elif self.NAME == 'android-iap':
            validated_receipt.get('raw_response', {}).get(attribute)

    def _get_transaction_id_from_receipt(self, validated_receipt):
        transaction_key = 'transaction_id' if self.NAME == 'ios-iap' else 'orderId'
        return self._get_attribute_from_receipt(validated_receipt, transaction_key)

    def _is_payment_redundant(self, basket_owner, original_transaction_id):
        return PaymentProcessorResponse.objects.filter(
            ~Q(basket__owner=basket_owner), extension__original_transaction_id=original_transaction_id).exists()
