import logging

from oscar.apps.payment.exceptions import GatewayError
from urllib.parse import urljoin
import waffle

from django.urls import reverse

from ecommerce.extensions.iap.api.v1.google_validator import GooglePlayValidator
from ecommerce.extensions.iap.models import IAPProcessorConfiguration
from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.payment.processors import BasePaymentProcessor, HandledProcessorResponse


logger = logging.getLogger(__name__)


class AndroidIAP(BasePaymentProcessor):
    """
    Android IAP Rest API.
    """
    NAME = 'android-iap'
    TITLE = 'AndroidInAppPurchase'
    DEFAULT_PROFILE_NAME = 'default'

    def __init__(self, site):
        """
        Constructs a new instance of the android IAP processor.

        Raises:
            KeyError: If a required setting is not configured for this payment processor
        """
        super(AndroidIAP, self).__init__(site)
        self.retry_attempts = IAPProcessorConfiguration.get_solo().retry_attempts
        self.google_validator = GooglePlayValidator()

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        """
        Generate a dictionary of Anrdroid IAP execution view api endpoint that is required to complete a transaction.

        Arguments:
            basket (Basket): The basket of products being purchased.
            request (Request, optional): A Request object which could be used to construct an absolute URL; not
                used by this method.
            use_client_side_checkout (bool, optional): Indicates if the Silent Order POST profile should be used.
            **kwargs: Additional parameters.

        Returns:
            dict: Android IAP speciific parameters required to complete a transaction.
        """
        return { 'payment_page_url': urljoin(get_ecommerce_url(), reverse('iap:iap-execute')) }

    def handle_processor_response(self, response, basket=None):
        """
        Execute an approved Android IAP payment.

        This method creates PaymentEvents and Sources for approved payments.

        Keyword Arguments:
            basket (Basket): Basket being purchased via the payment processor.

        Raises:
            GatewayError: Indicates a general error or unexpected behavior on the part of Android IAP system which prevented
                an approved payment from being executed.

        Returns:
            HandledProcessorResponse
        """
        available_attempts = 1
        product_id = response.get('productId')
        transaction_id = response.get('transactionId')
        if waffle.switch_is_active('IAP_RETRY_ATTEMPTS'):
            available_attempts = available_attempts + self.retry_attempts

        for attempt_count in range(1, available_attempts + 1):
            validation_reponse = self.google_validator.validate(response, self.configuration)
            validation_error = validation_reponse.get('error')
            if not validation_error:
                break

            entry = self.record_processor_response(validation_error, basket=basket)

            logger.warning(
                "Failed to execute android IAP payment for [%s] on attempt [%d]. "
                "Andoid IAP's response was recorded in entry [%d].",
                product_id,
                attempt_count,
                entry.id
            )

            # After utilizing all retry attempts, raise the exception 'GatewayError'
            if attempt_count == available_attempts:
                logger.error(
                    "Failed to execute android IAP payment for [%s]. "
                    "Android IAP's response was recorded in entry [%d].",
                    product_id,
                    entry.id
                )
                raise GatewayError

        self.record_processor_response(validation_reponse, transaction_id=transaction_id, basket=basket)
        order_id = validation_reponse['resource']['orderId']
        logger.info("Successfully executed android IAP payment [%s] for basket [%d].", order_id, basket.id)

        currency = basket.currency
        total = basket.total_incl_tax
        transaction_id = transaction_id
        email = basket.owner.email
        label = 'android IAP ({})'.format(email) if email else 'android IAP Account'

        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number=label,
            card_type=None
        )

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        raise NotImplementedError('The android IAP payment processor does not support credit issuance.')
