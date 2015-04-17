"""Payment processing classes containing logic specific to particular payment processors."""
# pylint: disable=abstract-method

import uuid
import logging
import datetime
from collections import OrderedDict

from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from ecommerce.extensions.payment.helpers import sign
from ecommerce.extensions.payment.errors import (
    ExcessiveMerchantDefinedData, UnsupportedProductError
)
from ecommerce.extensions.payment.constants import CybersourceConstants as CS


logger = logging.getLogger(__name__)


class BasePaymentProcessor(object):  # pragma no cover
    """Base payment processor class."""
    NAME = None
    DISPLAY_NAME = None

    def get_transaction_parameters(
            self,
            basket,
            receipt_page_url=None,
            cancel_page_url=None,
            merchant_defined_data=None
    ):
        """Generate a dictionary of transaction parameters to be sent to a payment processor."""
        raise NotImplementedError("Transaction parameters method not implemented.")

    def handle_processor_response(self, params):
        """ Handles the response from the payment processor """
        raise NotImplementedError("Processor response method not implemented.")

    @property
    def configuration(self):
        """
        Returns the configuration (set in Django settings) specific to this payment processor.

        Returns:
            dict: Payment processor configuration

        Raises:
            KeyError: If no settings found for this payment processor.
        """
        return settings.PAYMENT_PROCESSOR_CONFIG[self.NAME]


class Cybersource(BasePaymentProcessor):
    """CyberSource Secure Acceptance Web/Mobile (February 2015)

    For reference, see
    http://apps.cybersource.com/library/documentation/dev_guides/Secure_Acceptance_WM/Secure_Acceptance_WM.pdf.
    """
    NAME = CS.NAME
    DISPLAY_NAME = _(u'Credit Card')

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

    def get_transaction_parameters(
            self,
            basket,
            receipt_page_url=None,
            cancel_page_url=None,
            merchant_defined_data=None
    ):
        """Generate a dictionary of signed parameters CyberSource requires to complete a transaction.

        Arguments:
            basket (Basket): The basket whose line items are to be purchased as part of the transaction.

        Keyword Arguments:
            receipt_page_url (unicode): If provided, overrides the receipt page URL on the Secure Acceptance
                profile in use for this transaction.
            cancel_page_url (unicode): If provided, overrides the cancellation page URL on the Secure Acceptance
                profile in use for this transaction.
            merchant_defined_data (list of string): If provided, each element in this list is added to the
                transaction parameters, keyed under `merchant_defined_data<n>`, where `n` is the element's
                one-based index in the list. The list itself cannot contain more than 100 elements, and should
                not contain any personally identifying information.

        Returns:
            dict: CyberSource-specific parameters required to complete a transaction, including a signature.
        """
        transaction_parameters = self._get_raw_transaction_parameters(
            basket,
            receipt_page_url,
            cancel_page_url,
            merchant_defined_data
        )

        transaction_parameters[CS.FIELD_NAMES.SIGNATURE] = self._generate_signature(transaction_parameters)

        logger.info(
            u"Signed CyberSource transaction parameters for order [%s]",
            transaction_parameters.get(CS.FIELD_NAMES.REFERENCE_NUMBER)
        )

        return transaction_parameters

    def _get_raw_transaction_parameters(self, basket, receipt_page_url, cancel_page_url, merchant_defined_data):
        """Generate a dictionary of unsigned parameters CyberSource requires to complete a transaction.

        The 'signed_field_names' parameter should be a string containing a comma-separated list of all keys in
        the dictionary to be signed, including 'signed_field_names' itself. The value of this parameter is used
        to determine which parameters to sign, although the signing itself occurs separately.

        Arguments:
            basket (Basket): The basket whose line items are to be purchased as part of the transaction.
            receipt_page_url (unicode): Overrides the receipt page URL on the Secure Acceptance profile
                in use for this transaction.
            cancel_page_url (unicode): Overrides the cancellation page URL on the Secure Acceptance profile
                in use for this transaction.
            merchant_defined_data (list of string): Each element in this list is added to the transaction
                parameters, keyed under `merchant_defined_data<n>`, where `n` is the element's one-based index
                in the list. The list itself cannot contain more than 100 elements, and should not contain any
                personally identifying information.

        Returns:
            OrderedDict: CyberSource-specific parameters required to complete a transaction. An OrderedDict is
                used to facilitate testing. Keys are joined into a comma separated list which then signed to
                generate a digital signature. If the order of the keys is non-deterministic, then the signature
                might change, which could cause test failures. Testing aside, there's value in ensuring that the
                signatures we generate are deterministic and reproducible.

        Raises:
            ExcessiveMerchantDefinedData: If the provided merchant-defined data exceeds CyberSource's
                optional field limit.
        """
        parameters = OrderedDict()

        # Access token used for authentication with Secure Acceptance.
        parameters[CS.FIELD_NAMES.ACCESS_KEY] = self.access_key

        # Identifier representing the Secure Acceptance profile to use with this transaction.
        parameters[CS.FIELD_NAMES.PROFILE_ID] = self.profile_id

        # Identifier representing the charge to which this transaction relates; must be a string.
        # For context, say you were to perform a charge as a two-step process where you initially
        # authorize through Secure Acceptance, then later process the settlement. Although they
        # are two separate transactions, when taken together the authorization and the settlement
        # constitute one charge. As such, they would be assigned the same reference number.
        parameters[CS.FIELD_NAMES.REFERENCE_NUMBER] = basket.id

        # Unique identifier associated with this transaction; must be a string.
        parameters[CS.FIELD_NAMES.TRANSACTION_UUID] = uuid.uuid4().hex

        # One of the Secure Acceptance transaction types.
        parameters[CS.FIELD_NAMES.TRANSACTION_TYPE] = CS.TRANSACTION_TYPE

        # One of the Secure Acceptance payment methods.
        parameters[CS.FIELD_NAMES.PAYMENT_METHOD] = CS.PAYMENT_METHOD

        # ISO currency code representing the currency in which to conduct the transaction.
        parameters[CS.FIELD_NAMES.CURRENCY] = basket.currency

        # Total amount to be charged. May contain numeric characters and a decimal point; must be a string.
        parameters[CS.FIELD_NAMES.AMOUNT] = unicode(basket.total_excl_tax)

        # IETF language tag representing the language to use for customer-facing content.
        parameters[CS.FIELD_NAMES.LOCALE] = self.language_code

        if receipt_page_url:
            parameters[CS.FIELD_NAMES.OVERRIDE_CUSTOM_RECEIPT_PAGE] = receipt_page_url
        elif self.receipt_page_url:
            parameters[CS.FIELD_NAMES.OVERRIDE_CUSTOM_RECEIPT_PAGE] = self._generate_receipt_url(basket)

        if cancel_page_url:
            parameters[CS.FIELD_NAMES.OVERRIDE_CUSTOM_CANCEL_PAGE] = cancel_page_url
        elif self.cancel_page_url:
            parameters[CS.FIELD_NAMES.OVERRIDE_CUSTOM_CANCEL_PAGE] = self.cancel_page_url

        if merchant_defined_data:
            if len(merchant_defined_data) > CS.MAX_OPTIONAL_FIELDS:
                raise ExcessiveMerchantDefinedData
            else:
                for n, data in enumerate(merchant_defined_data, start=1):
                    parameters[CS.FIELD_NAMES.MERCHANT_DEFINED_DATA_BASE + unicode(n)] = data

        # A string in ISO 8601 format representing the time at which the transaction parameters were signed.
        parameters[CS.FIELD_NAMES.SIGNED_DATE_TIME] = datetime.datetime.utcnow().strftime(CS.ISO_8601_FORMAT)

        # Transaction parameters which are to be signed or unsigned; must be strings containing comma-separated keys.
        parameters[CS.FIELD_NAMES.UNSIGNED_FIELD_NAMES] = CS.UNSIGNED_FIELD_NAMES
        parameters[CS.FIELD_NAMES.SIGNED_FIELD_NAMES] = CS.UNSIGNED_FIELD_NAMES
        # NOTE: This currently joins all keys in the dictionary, and as such should be the last item added to
        # the parameters dictionary before returning it.
        parameters[CS.FIELD_NAMES.SIGNED_FIELD_NAMES] = CS.SEPARATOR.join(parameters.keys())

        logger.info(u"Generated unsigned CyberSource transaction parameters for basket [%s]", basket.id)

        return parameters

    def _generate_receipt_url(self, order):
        """Generate the full receipt URL based off the order.

        Takes the receipt page URL and modifies it to display a single order.

        Args:
            order (Order): The order the receipt represents

        Returns:
            string: The string representation of the receipt URL for this order.

        """
        return "{base_url}?payment-order-num={order_number}".format(
            base_url=self.receipt_page_url, order_number=order.id
        )

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
        target_parameters = parameters[CS.FIELD_NAMES.SIGNED_FIELD_NAMES].split(CS.SEPARATOR)
        # Generate a comma-separated list of keys and values to be signed. CyberSource refers to this
        # as a 'Version 1' signature in their documentation.
        message = CS.SEPARATOR.join(
            [CS.MESSAGE_SUBSTRUCTURE.format(
                key=key, value=parameters.get(key)
            ) for key in target_parameters]
        )

        return sign(message, self.secret_key)


class SingleSeatCybersource(Cybersource):
    """Payment Processor limited to supporting a single seat. """

    def _generate_receipt_url(self, order):
        """Generate the full receipt URL based off the order.

        Takes the receipt page URL and modifies it to display a single order.

        Args:
            order (Order): The order the receipt represents

        Returns:
            string: The string representation of the receipt URL for this order.

        """
        # TODO: Right now, our receipt page only supports the purchase of Course Seats, and assumes that an order
        # is relative to a single course. This function will try and get a course ID to construct the URL. Once our
        # receipt page supports donations, cohorts, and other products, we will need a generic URL that can be
        # constructed simply from the order number.
        # This issue should be resolved by completing JIRA Ticket XCOM-202
        line = order.lines.all()[0]
        if line and line.product.get_product_class().name == 'Seat':
            course_key = line.product.attribute_values.get(attribute__name="course_key").value
            return "{base_url}{course_key}/?payment-order-num={order_number}".format(
                base_url=self.receipt_page_url, course_key=course_key, order_number=order.id
            )
        else:
            msg = (
                u'Cannot construct a receipt URL for order [{order_number}]. Receipt page only supports Seat products.'
                .format(order_number=order.id)
            )
            logger.error(msg)
            raise UnsupportedProductError(msg)
