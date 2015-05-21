import abc

from django.conf import settings
from oscar.core.loading import get_model

PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class BasePaymentProcessor(object):  # pragma: no cover
    """Base payment processor class."""
    __metaclass__ = abc.ABCMeta

    NAME = None

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
