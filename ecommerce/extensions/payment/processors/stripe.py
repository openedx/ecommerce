""" Stripe payment processing. """
from __future__ import absolute_import, unicode_literals
import logging
from urlparse import urljoin

from django.conf import settings
from django.core.urlresolvers import reverse
from oscar.apps.payment.exceptions import GatewayError

from oscar.core.loading import get_model
import stripe

from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.processors import BasePaymentProcessor

logger = logging.getLogger(__name__)

PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class Stripe(BasePaymentProcessor):
    NAME = 'stripe'

    def __init__(self):
        """
        Constructs a new instance of the Stripe processor.

        Raises:
            KeyError: If no settings configured for this payment processor
            AttributeError: If ECOMMERCE_URL_ROOT setting is not set.
        """
        configuration = self.configuration
        self.publishable_key = configuration['publishable_key']
        self.secret_key = configuration['secret_key']
        self.receipt_page_url = configuration['receipt_page_url']
        self.image_url = configuration['image_url']
        self.ecommerce_url_root = settings.ECOMMERCE_URL_ROOT

        stripe.api_key = self.secret_key

    def get_transaction_parameters(self, basket, request=None):
        return {
            'payment_page_url': urljoin(self.ecommerce_url_root, reverse('stripe_checkout')),
            'key': self.publishable_key,
            'amount': self._dollars_to_cents(basket.total_incl_tax),
            'currency': basket.currency,
            'name': settings.PLATFORM_NAME,
            'description': '',  # TODO Seat title
            'image': self.image_url,
            'bitcoin': True,
            'alipay': 'auto',
            'locale': 'auto'
        }

    def _dollars_to_cents(self, dollars):
        return unicode((dollars * 100).to_integral())

    def handle_processor_response(self, response, basket=None):
        token = response
        # Create the charge on Stripe's servers - this will charge the user's card
        try:
            charge = stripe.Charge.create(
                amount=self._dollars_to_cents(basket.total_incl_tax),
                currency="usd",
                source=token,
                description="Example charge"
            )
            logger.info(charge)

            source_type, __ = SourceType.objects.get_or_create(name=self.NAME)
            currency = basket.currency
            total = basket.total_incl_tax
            transaction_id = charge.id

            source = Source(source_type=source_type,
                            currency=currency,
                            amount_allocated=total,
                            amount_debited=total,
                            reference=transaction_id,
                            label='Stripe',
                            card_type=None)

            # Create PaymentEvent to track
            event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.PAID)
            event = PaymentEvent(event_type=event_type, amount=total, reference=transaction_id,
                                 processor_name=self.NAME)

            return source, event
        except stripe.error.CardError, e:
            # The card has been declined
            logger.exception('Payment failed!')

    def _record_refund(self, source, amount):
        transaction_id = source.reference
        order = source.order

        source.refund(amount, reference=transaction_id)

        event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.REFUNDED)
        PaymentEvent.objects.create(event_type=event_type, order=order, amount=amount, reference=transaction_id,
                                    processor_name=self.NAME)

    def issue_credit(self, source, amount, currency):
        transaction_id = source.reference

        try:
            charge = stripe.Charge.retrieve(transaction_id)
            charge.refunds.create(amount=self._dollars_to_cents(amount))
            self._record_refund(source, amount)
        except stripe.error.CardError:
            logger.exception('Refund of Stripe charge [%s] failed!', transaction_id)
            raise GatewayError
