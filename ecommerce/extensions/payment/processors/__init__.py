import abc

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext as _
from oscar.core.loading import get_model
import waffle


PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class BasePaymentProcessor(object):  # pragma: no cover
    """Base payment processor class."""
    __metaclass__ = abc.ABCMeta

    NAME = None

    STANDARD_BUTTON_TEMPLATE = u"""
    <button class="{button_class}" value="{processor_name}">
        {button_label}
    </button>
    """.strip()

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

    def render_payment_button(self, basket, user):
        """
        This function renders a payment button to any page for which payment using this processor is enabled
        usually the rendered button will look similar to:

            <button class="btn btn-success payment-button payment-handler builtin-handling">
                Pay using our processor
            </button>

        To render such a button please use

        Returns:
            str

        """
        return self.STANDARD_BUTTON_TEMPLATE.format(
            button_class=self.payment_button_classes,
            button_label=self.payment_label,
            processor_name=self.NAME
        )

    @property
    def payment_label(self):
        return _(u"Checkout with {processor_name}").format(
            processor_name=self.NAME.capitalize()
        )

    @property
    def payment_button_classes(self):
        return u"btn btn-success payment-button builtin-handling"

    def get_payment_page_script(self, basket, user):
        return None

    @abc.abstractmethod
    def handle_processor_response(self, response, basket=None):
        """
        Handle a response from the payment processor.

        This method creates PaymentEvents and Sources for successful payments,
        raising the exception from this method means payment fails.

        Arguments:
            response (dict): Dictionary of parameters received from the payment processor

        Keyword Arguments:
            basket (Basket): Basket whose contents have been purchased via the payment processor

        Raises:
            any exception raised from this method will delete the basket, and mean failed
            payment.
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
        try:
            return settings.PAYMENT_PROCESSOR_CONFIG[self.NAME]
        except KeyError:
            raise ImproperlyConfigured("No configuration for {} processor".format(self.NAME))

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
