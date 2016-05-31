""" PayPal payment processing. """
from decimal import Decimal
import logging
from urlparse import urljoin

from django.core.urlresolvers import reverse
from django.utils.functional import cached_property
from oscar.apps.payment.exceptions import GatewayError
from oscar.core.loading import get_model
import paypalrestsdk
import waffle

from ecommerce.core.url_utils import get_ecommerce_url, get_lms_url
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.processors import BasePaymentProcessor
from ecommerce.extensions.payment.models import PaypalWebProfile
from ecommerce.extensions.payment.utils import middle_truncate


logger = logging.getLogger(__name__)

PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
ProductClass = get_model('catalogue', 'ProductClass')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class Paypal(BasePaymentProcessor):
    """
    PayPal REST API (May 2015)

    For reference, see https://developer.paypal.com/docs/api/.
    """

    NAME = u'paypal'
    DEFAULT_PROFILE_NAME = 'default'

    def __init__(self):
        """
        Constructs a new instance of the PayPal processor.

        Raises:
            KeyError: If a required setting is not configured for this payment processor
        """
        # Number of times payment execution is retried after failure.
        self.retry_attempts = self.configuration.get('retry_attempts', 1)

    @cached_property
    def paypal_api(self):
        """
        Returns Paypal API instance with appropriate configuration
        Returns: Paypal API instance
        """
        return paypalrestsdk.Api({
            'mode': self.configuration['mode'],
            'client_id': self.configuration['client_id'],
            'client_secret': self.configuration['client_secret']
        })

    @property
    def receipt_url(self):
        return get_lms_url(self.configuration['receipt_path'])

    @property
    def cancel_url(self):
        return get_lms_url(self.configuration['cancel_path'])

    @property
    def error_url(self):
        return get_lms_url(self.configuration['error_path'])

    def get_transaction_parameters(self, basket, request=None):
        """
        Create a new PayPal payment.

        Arguments:
            basket (Basket): The basket of products being purchased.

        Keyword Arguments:
            request (Request): A Request object which is used to construct PayPal's `return_url`.

        Returns:
            dict: PayPal-specific parameters required to complete a transaction. Must contain a URL
                to which users can be directed in order to approve a newly created payment.

        Raises:
            GatewayError: Indicates a general error or unexpected behavior on the part of PayPal which prevented
                a payment from being created.
        """
        return_url = urljoin(get_ecommerce_url(), reverse('paypal_execute'))
        data = {
            'intent': 'sale',
            'redirect_urls': {
                'return_url': return_url,
                'cancel_url': self.cancel_url,
            },
            'payer': {
                'payment_method': 'paypal',
            },
            'transactions': [{
                'amount': {
                    'total': unicode(basket.total_incl_tax),
                    'currency': basket.currency,
                },
                'item_list': {
                    'items': [
                        {
                            'quantity': line.quantity,
                            # PayPal requires that item names be at most 127 characters long.
                            'name': middle_truncate(line.product.title, 127),
                            # PayPal requires that the sum of all the item prices (where price = price * quantity)
                            # equals to the total amount set in amount['total'].
                            'price': unicode(line.line_price_incl_tax_incl_discounts / line.quantity),
                            'currency': line.stockrecord.price_currency,
                        }
                        for line in basket.all_lines()
                    ],
                },
                'invoice_number': basket.order_number,
            }],
        }

        try:
            web_profile = PaypalWebProfile.objects.get(name=self.DEFAULT_PROFILE_NAME)
            data['experience_profile_id'] = web_profile.id
        except PaypalWebProfile.DoesNotExist:
            pass

        payment = paypalrestsdk.Payment(data, api=self.paypal_api)
        payment.create()

        # Raise an exception for payments that were not successfully created. Consuming code is
        # responsible for handling the exception.
        if not payment.success():
            error = self._get_error(payment)
            entry = self.record_processor_response(error, transaction_id=error['debug_id'], basket=basket)  # pylint: disable=unsubscriptable-object

            logger.error(
                u"Failed to create PayPal payment for basket [%d]. PayPal's response was recorded in entry [%d].",
                basket.id,
                entry.id
            )

            raise GatewayError(error)

        entry = self.record_processor_response(payment.to_dict(), transaction_id=payment.id, basket=basket)
        logger.info(u"Successfully created PayPal payment [%s] for basket [%d].", payment.id, basket.id)

        for link in payment.links:
            if link.rel == 'approval_url':
                approval_url = link.href
                break
        else:
            logger.error(
                u"Approval URL missing from PayPal payment [%s]. PayPal's response was recorded in entry [%d].",
                payment.id,
                entry.id
            )
            raise GatewayError(
                'Approval URL missing from PayPal payment response. See entry [{}] for details.'.format(entry.id))

        parameters = {
            'payment_page_url': approval_url,
        }

        return parameters

    def handle_processor_response(self, response, basket=None):
        """
        Execute an approved PayPal payment.

        This method creates PaymentEvents and Sources for approved payments.

        Arguments:
            response (dict): Dictionary of parameters returned by PayPal in the `return_url` query string.

        Keyword Arguments:
            basket (Basket): Basket being purchased via the payment processor.

        Raises:
            GatewayError: Indicates a general error or unexpected behavior on the part of PayPal which prevented
                an approved payment from being executed.
        """
        data = {'payer_id': response.get('PayerID')}

        # By default PayPal payment will be executed only once.
        available_attempts = 1

        # Add retry attempts (provided in the configuration)
        # if the waffle switch 'ENABLE_PAYPAL_RETRY' is set
        if waffle.switch_is_active('PAYPAL_RETRY_ATTEMPTS'):
            available_attempts = available_attempts + self.retry_attempts

        for attempt_count in range(1, available_attempts + 1):

            payment = paypalrestsdk.Payment.find(response.get('paymentId'), api=self.paypal_api)
            payment.execute(data)

            if payment.success():
                # On success break the loop.
                break

            # Raise an exception for payments that were not successfully executed. Consuming code is
            # responsible for handling the exception
            error = self._get_error(payment)
            entry = self.record_processor_response(error, transaction_id=error['debug_id'], basket=basket)  # pylint: disable=unsubscriptable-object

            logger.warning(
                u"Failed to execute PayPal payment on attempt [%d]. "
                u"PayPal's response was recorded in entry [%d].",
                attempt_count,
                entry.id
            )

            # After utilizing all retry attempts, raise the exception 'GatewayError'
            if attempt_count == available_attempts:
                logger.error(
                    u"Failed to execute PayPal payment [%s]. "
                    u"PayPal's response was recorded in entry [%d].",
                    payment.id,
                    entry.id
                )
                raise GatewayError

        self.record_processor_response(payment.to_dict(), transaction_id=payment.id, basket=basket)
        logger.info(u"Successfully executed PayPal payment [%s] for basket [%d].", payment.id, basket.id)

        # Get or create Source used to track transactions related to PayPal
        source_type, __ = SourceType.objects.get_or_create(name=self.NAME)
        currency = payment.transactions[0].amount.currency
        total = Decimal(payment.transactions[0].amount.total)
        transaction_id = payment.id
        # payer_info.email may be None, see:
        # http://stackoverflow.com/questions/24090460/paypal-rest-api-return-empty-payer-info-for-non-us-accounts
        email = payment.payer.payer_info.email
        label = 'PayPal ({})'.format(email) if email else 'PayPal Account'

        source = Source(
            source_type=source_type,
            currency=currency,
            amount_allocated=total,
            amount_debited=total,
            reference=transaction_id,
            label=label,
            card_type=None
        )

        # Create PaymentEvent to track payment
        event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.PAID)
        event = PaymentEvent(event_type=event_type, amount=total, reference=transaction_id, processor_name=self.NAME)

        return source, event

    def _get_error(self, payment):
        """
        Shameful workaround for mocking the `error` attribute on instances of
        `paypalrestsdk.Payment`. The `error` attribute is created at runtime,
        but passing `create=True` to `patch()` isn't enough to mock the
        attribute in this module.
        """
        return payment.error  # pragma: no cover

    def _get_payment_sale(self, payment):
        """
        Returns the Sale related to a given Payment.

        Note (CCB): We mostly expect to have a single sale and transaction per payment. If we
        ever move to a split payment scenario, this will need to be updated.
        """
        for transaction in payment.transactions:
            for related_resource in transaction.related_resources:
                try:
                    return related_resource.sale
                except Exception:   # pylint: disable=broad-except
                    continue

        return None

    def issue_credit(self, source, amount, currency):
        order = source.order

        try:
            payment = paypalrestsdk.Payment.find(source.reference, api=self.paypal_api)
            sale = self._get_payment_sale(payment)

            if not sale:
                logger.error('Unable to find a Sale associated with PayPal Payment [%s].', payment.id)

            refund = sale.refund({
                'amount': {
                    'total': unicode(amount),
                    'currency': currency,
                }
            })

        except:
            msg = 'An error occurred while attempting to issue a credit (via PayPal) for order [{}].'.format(
                order.number)
            logger.exception(msg)
            raise GatewayError(msg)

        basket = order.basket
        if refund.success():
            transaction_id = refund.id

            self.record_processor_response(refund.to_dict(), transaction_id=transaction_id, basket=basket)

            source.refund(amount, reference=transaction_id)

            event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.REFUNDED)
            PaymentEvent.objects.create(event_type=event_type, order=order, amount=amount, reference=transaction_id,
                                        processor_name=self.NAME)
        else:
            error = refund.error
            entry = self.record_processor_response(error, transaction_id=error['debug_id'], basket=basket)

            msg = "Failed to refund PayPal payment [{sale_id}]. " \
                  "PayPal's response was recorded in entry [{response_id}].".format(sale_id=sale.id,
                                                                                    response_id=entry.id)
            raise GatewayError(msg)

        return True
