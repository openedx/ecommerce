from __future__ import unicode_literals

import abc

import waffle
from django.conf import settings
from oscar.core.loading import get_model

from ecommerce.extensions.payment.constants import CLIENT_SIDE_CHECKOUT_FLAG_NAME

PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class BasePaymentProcessor(object):  # pragma: no cover
    """Base payment processor class."""
    __metaclass__ = abc.ABCMeta

    # NOTE: Ensure that, if passed to a Django template, Django does not attempt to instantiate this class
    # or its children. Doing so without a Site object will cause issues.
    # See https://docs.djangoproject.com/en/1.8/ref/templates/api/#variables-and-lookups
    do_not_call_in_templates = True

    NAME = None

    def __init__(self, site):
        super(BasePaymentProcessor, self).__init__()
        self.site = site

    @abc.abstractmethod
    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        """
        Generate a dictionary of signed parameters required for this processor to complete a transaction.

        Arguments:
            use_client_side_checkout:
            basket (Basket): The basket of products being purchased.
            request (Request, optional): A Request object which can be used to construct an absolute URL in
                cases where one is required.
            use_client_side_checkout (bool, optional): Determines if client-side checkout should be used.
            **kwargs: Additional parameters.

        Returns:
            dict: Payment processor-specific parameters required to complete a transaction. At a minimum,
                this dict must include a `payment_page_url` indicating the location of the processor's
                hosted payment page.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def handle_processor_response(self, response, basket=None):
        """
        Handle a response from the payment processor.

        This method creates PaymentEvents and Sources for successful payments.

        Arguments:
            response (dict): Dictionary of parameters received from the payment processor

        Keyword Arguments:
            basket (Basket): Basket whose contents have been purchased via the payment processor
        """
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
        partner_short_code = self.site.siteconfiguration.partner.short_code
        return settings.PAYMENT_PROCESSOR_CONFIG[partner_short_code.lower()][self.NAME.lower()]

    @property
    def client_side_payment_url(self):
        """
        Returns the URL to which payment data, collected directly from the payment page, should be posted.

        If the payment processor does not support client-side payments, ``None`` will be returned.

        Returns:
            str
        """
        return None

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

    @abc.abstractmethod
    def issue_credit(self, source, amount, currency):
        """
        Issue a credit for the specified transaction.

        Arguments:
            source (Source): Payment Source used for the original debit/purchase.
            amount (Decimal): amount to be credited/refunded
            currency (string): currency of the amount to be credited
        """
        raise NotImplementedError

    @classmethod
    def is_enabled(cls):
        """
        Returns True if this payment processor is enabled, and False otherwise.
        """
        return waffle.switch_is_active(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + cls.NAME)
