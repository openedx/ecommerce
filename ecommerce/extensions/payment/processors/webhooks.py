""" Webhooks handling for payment processing. """


import logging

import stripe
from oscar.apps.partner import strategy
from oscar.core.loading import get_class, get_model

from ecommerce.extensions.analytics.utils import track_segment_event
from ecommerce.extensions.basket.utils import get_billing_address_from_payment_intent_data
from ecommerce.extensions.checkout.mixins import EdxOrderPlacementMixin
from ecommerce.extensions.payment.processors import BasePaymentProcessor, HandledProcessorResponse
from ecommerce.extensions.payment.processors.stripe import Stripe

logger = logging.getLogger(__name__)

Basket = get_model('basket', 'Basket')
OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


class StripeWebhooksProcessor(EdxOrderPlacementMixin, BasePaymentProcessor):
    """
    Handle a payment success received through Stripe webhooks.
    """

    NAME = 'stripe'

    def __init__(self, site):
        """
        Constructs a new instance of the Stripe webhooks processor.

        Raises:
            KeyError: If no settings configured for this payment processor.
        """
        super(StripeWebhooksProcessor, self).__init__(site)
        self.site = site

    @property
    def payment_processor(self):
        return Stripe(self.site)

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        raise NotImplementedError

    def handle_processor_response(self, response, basket=None):
        raise NotImplementedError

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        raise NotImplementedError

    def _get_address_from_token(self, payment_intent_id):
        """
        Retrieves the billing address associated with a PaymentIntent.

        Returns:
            BillingAddress
        """
        retrieve_kwargs = {
            'expand': ['payment_method'],
        }

        payment_intent = stripe.PaymentIntent.retrieve(
            payment_intent_id,
            **retrieve_kwargs,
        )

        return get_billing_address_from_payment_intent_data(payment_intent)

    def handle_webhooks_payment(self, request, payment_intent, payment_method_type):
        """
        Upon receipt of the payment_intent.succeeded event from Stripe, create an order, create a billing address,
        fulfill order, and save payment processor data.
        """
        # Get basket associated to the Payment Intent
        payment_intent_id = payment_intent['id']
        order_number = payment_intent['description']
        basket_id = OrderNumberGenerator().basket_id(order_number)
        try:
            basket = Basket.objects.get(id=basket_id)
            basket.strategy = strategy.Default()
        except Basket.DoesNotExist:
            logger.exception(
                '[Dynamic Payment Methods] Basket with ID %d does not exist.'
                'This was attempted for for order %s and Payment Intent %s',
                basket_id, order_number, payment_intent_id
            )
        else:
            # Record successful processor response, record payment, and track event
            total = basket.total_incl_tax
            currency = basket.currency

            properties = {
                'basket_id': basket.id,
                'processor_name': self.NAME,
                'stripe_enabled': True,
            }
            try:
                self.record_processor_response(payment_intent, transaction_id=payment_intent_id, basket=basket)
                logger.info(
                    '[Dynamic Payment Methods] Successfully recorded Stripe payment intent [%s] '
                    'for basket [%d] and order number [%s].',
                    payment_intent_id,
                    basket.id,
                    basket.order_number,
                )
            except Exception as ex:
                properties.update({'success': False, 'payment_error': type(ex).__name__, })
                raise
            else:
                # Card number is required for Source object, it cannot be null (payment_source.label)
                # Dynamic payment methods payment intents do not contain card information, adding DPM type instead.
                label = 'stripe {}'.format(payment_method_type)
                handled_processor_response = HandledProcessorResponse(
                    transaction_id=payment_intent_id,
                    total=total,
                    currency=currency,
                    card_number=label,
                    card_type=None
                )
                self.record_payment(basket, handled_processor_response)
                properties.update({'total': handled_processor_response.total, 'success': True, })
            finally:
                # TODO: Differentiate event from regular payments?
                track_segment_event(basket.site, basket.owner, 'Payment Processor Response', properties)

            # Create Billing Address
            billing_address_obj = self._get_address_from_token(payment_intent_id)
            try:
                billing_address = self.create_billing_address(
                    user=basket.owner,
                    billing_address=billing_address_obj
                )
            except Exception as err:  # pylint: disable=broad-except
                logger.exception(
                    '[Dynamic Payment Methods] Error creating billing address for basket [%d]: %s',
                    basket.id, err
                )
                billing_address = None

            try:
                order = self.create_order(request, basket, billing_address)
                self.handle_post_order(order)
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    '[Dynamic Payment Methods] Error processing order for transaction [%s], '
                    'with order [%s] and basket [%d]. Processed by [%s].',
                    payment_intent_id,
                    basket.order_number,
                    basket.id,
                    'stripe',
                )
