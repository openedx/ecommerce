

import abc
import logging
from collections import namedtuple

import waffle
from django.conf import settings
from django.utils.functional import cached_property
from oscar.core.loading import get_model

PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')

HandledProcessorResponse = namedtuple('HandledProcessorResponse',
                                      ['transaction_id', 'total', 'currency', 'card_number', 'card_type'])

logger = logging.getLogger(__name__)


class BasePaymentProcessor(metaclass=abc.ABCMeta):  # pragma: no cover
    """Base payment processor class."""

    # NOTE: Ensure that, if passed to a Django template, Django does not attempt to instantiate this class
    # or its children. Doing so without a Site object will cause issues.
    # See https://docs.djangoproject.com/en/1.8/ref/templates/api/#variables-and-lookups
    do_not_call_in_templates = True

    NAME = None
    # The title will be used in user-facing templates
    TITLE = None

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

        Returns:
            HandledProcessorResponse
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
    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        """
        Issue a credit/refund for the specified transaction.

        Arguments:
            order_number (str): Order number of the order being refunded.
            basket (Basket): Basket associated with the order being refunded.
            reference_number (str): Reference number of the transaction being refunded.
            amount (Decimal): amount to be credited/refunded
            currency (string): currency of the amount to be credited

        Returns:
            str: Reference number of the *refund* transaction. Unless the payment processor groups related transactions,
             this will *NOT* be the same as the `reference_number` argument.
        """
        raise NotImplementedError

    @classmethod
    def is_enabled(cls):
        """
        Returns True if this payment processor is enabled, and False otherwise.
        """
        return waffle.switch_is_active(settings.PAYMENT_PROCESSOR_SWITCH_PREFIX + cls.NAME)


class BaseClientSidePaymentProcessor(BasePaymentProcessor, metaclass=abc.ABCMeta):  # pylint: disable=abstract-method
    """ Base class for client-side payment processors. """

    def get_template_name(self):
        """ Returns the path of the template to be loaded for this payment processor.

        Returns:
            str
        """
        return 'payment/{}.html'.format(self.NAME)


class ApplePayMixin:
    @cached_property
    def apple_pay_merchant_id_domain_association(self):
        """ Returns the Apple Pay merchant domain association contents that will be served at
        /.well-known/apple-developer-merchantid-domain-association.

        Returns:
            str
        """
        return (self.configuration.get('apple_pay_merchant_id_domain_association') or '').strip()
