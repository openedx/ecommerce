import abc
import importlib

from django.utils.translation import ugettext_lazy as _
from oscar.core.loading import get_model

PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class BasePaymentProcessor(object):  # pragma: no cover
    """Base payment processor class."""
    __metaclass__ = abc.ABCMeta

    CHECKOUT_BUTTON_LABEL = _('Checkout')
    CONFIGURATION_MODEL = None
    NAME = None
    URLS_MODULE = None

    def __init__(self, site=None):
        self._configuration = None
        self.site = site

    @abc.abstractmethod
    def get_transaction_parameters(self, basket, request=None):
        """
        Generate a dictionary of signed parameters required for this processor to complete a transaction.

        Arguments:
            basket (Basket): The basket of products being purchased.

        Keyword Arguments:
            request (Request): A Request object which can be used to construct an absolute URL in
                cases where one is required.

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
            MissingRequestError: if no `request` is available
        """
        if self._configuration is not None:
            return self._configuration

        if self.CONFIGURATION_MODEL:
            module_name, class_name = self.CONFIGURATION_MODEL.rsplit('.', 1)
            m = importlib.import_module(module_name)
            Configuration = getattr(m, class_name)
            try:
                self._configuration = Configuration.objects.get(site=self.site, active=True)
            except Configuration.DoesNotExist:
                pass

        return self._configuration

    @property
    def is_enabled(self):
        configuration = self.configuration
        return configuration and configuration.active

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
