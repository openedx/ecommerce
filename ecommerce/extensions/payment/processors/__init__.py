import abc

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import ugettext as _
from oscar.core.loading import get_model
from threadlocals.threadlocals import get_current_request
import waffle

from ecommerce.core.exceptions import MissingRequestError
from ecommerce.core.url_utils import get_lms_url

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

    @property
    def receipt_url(self):
        return get_lms_url(self.configuration['receipt_path'])

    @property
    def cancel_url(self):
        return get_lms_url(self.configuration['cancel_path'])

    @property
    def error_url(self):
        return get_lms_url(self.configuration['error_path'])

    @property
    def payment_label(self):
        """
        Returns: Label for payment button on the basket page
        """
        return _(u"Checkout with {processor_name}").format(
            processor_name=self.NAME.capitalize()
        )

    @property
    def default_checkout_handler(self):
        """
        Specifies whether this processor instance is handled by the default handler
        on the checkout page.

        Returns: True if this basket uses default check out logic in javascript
        on the basket Page.
        """
        return True

    # pylint: disable=unused-argument
    # Note parameters used in subclasses
    def get_basket_page_script(self, basket, user):
        """
        Returns a script to be attached to basket page.

        Returns: A string or None. If returns a string this string will be attached at the
        bottom of a checkout page, intended use is to attach a <script> tag that will
        handle given processor.
        """
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
            PaymentError: Means there is an error during Payment.
            Exception: any exception raised from this method will delete the basket, and mean failed
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
            MissingRequestError: if no `request` is available
            ImproperlyConfigured: If no settings found for this payment processor
        """
        request = get_current_request()
        if request:
            partner_short_code = request.site.siteconfiguration.partner.short_code
            try:
                return settings.PAYMENT_PROCESSOR_CONFIG[partner_short_code.lower()][self.NAME.lower()]
            except KeyError:
                raise ImproperlyConfigured("No configuration for {} processor".format(self.NAME.lower()))
        raise MissingRequestError

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
