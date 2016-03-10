""" Stripe payment processing. """
from __future__ import absolute_import, unicode_literals
import logging
from urlparse import urljoin

from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.loader import get_template
from django.utils.translation import ugettext as _
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


class StripeProcessor(BasePaymentProcessor):

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

    def get_transaction_parameters(self, basket, request=None):
        return {
            'payment_page_url': urljoin(self.ecommerce_url_root, reverse('stripe_payment')),
            'basket': basket.pk
        }

    def _get_button_context(self, basket, user):
        ctx = self.get_stripe_template_data(user, basket)
        ctx.update({
            "basket": basket
        })
        return ctx

    @property
    def payment_label(self):
        return _("Checkout using Credit-Card")

    @property
    def payment_button_classes(self):
        return "btn btn-success payment-button stripe"

    def get_payment_page_script(self, basket, user):
        template = get_template("payment/processors/stripe_paymentscript.html")
        return template.render(self._get_button_context(basket, user))

    def get_total(self, basket):
        # Throw error if any rounding occours
        dollars_to_cents = lambda dollars: unicode((dollars * 100).to_integral_exact())
        return dollars_to_cents(basket.total_incl_tax)

    def get_description(self, basket):
        return _("Payment for order {order_sku} for {platform_name}").format(
            order_sku=basket.order_number,
            platform_name=settings.PLATFORM_NAME
        )

    def get_stripe_template_data(self, user, basket):
        return {
            'stripe_publishable_key': self.publishable_key,
            'stripe_process_payment_url': reverse('stripe_checkout', kwargs={
                'basket': basket.pk
            }),
            'stripe_amount_cents': self.get_total(basket),
            'stripe_image_url': self.image_url,
            'stripe_currency': basket.currency,
            'stripe_user_email': user.email,
            # TODO: Description could describe payment more.
            'stripe_payment_description': self.get_description(basket),
            'button_label': self.payment_label
        }

    def handle_processor_response(self, response, basket=None):
        token = response
        # Create the charge on Stripe's servers - this will charge the user's card
        try:
            charge = stripe.Charge.create(
                amount=self.get_total(basket),
                currency=basket.currency,
                source=token,
                api_key=self.secret_key,
                description=self.get_description(basket),
                metadata={
                    'basket_pk': basket.pk,
                    'basket_sku': basket.order_number,
                    'username': basket.owner.username
                }
            )
            logger.info(charge)

            source_type, __ = SourceType.objects.get_or_create(name=self.NAME)
            currency = basket.currency
            total = basket.total_incl_tax
            transaction_id = charge.id

            # TODO: stripe guarantees that transaction_id is shorter than 255
            # and reference is 128 long
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
        except stripe.error.CardError as e:
            # The card has been declined
            logger.exception('Payment failed!')

    def _record_refund(self, source, amount):
        transaction_id = source.reference
        order = source.order

        source.refund(amount, reference=transaction_id)

        event_type, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.REFUNDED)
        PaymentEvent.objects.create(event_type=event_type, order=order, amount=amount, reference=transaction_id,
                                    processor_name=self.NAME)

    # TODO: Remove this note: issues refund for a given transaction
    def issue_credit(self, source, amount, currency):

        # TODO: Technically stripe guarantees all fields to be shorter than 255
        # chars and reference 128 chars long (from: AbstractSource)
        transaction_id = source.reference

        try:
            stripe.Refund.create(
                charge=transaction_id,
                api_key=self.secret_key
            )
            self._record_refund(source, amount)
        except stripe.error.CardError:
            logger.exception('Refund of Stripe charge [%s] failed!', transaction_id)
            raise GatewayError
