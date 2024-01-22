""" Stripe payment processing. """


import logging

import stripe
from oscar.apps.payment.exceptions import GatewayError
from oscar.core.loading import get_model

from ecommerce.core.url_utils import get_ecommerce_url
from ecommerce.extensions.basket.constants import PAYMENT_INTENT_ID_ATTRIBUTE
from ecommerce.extensions.basket.models import Basket
from ecommerce.extensions.basket.utils import (
    basket_add_payment_intent_id_attribute,
    get_billing_address_from_payment_intent_data
)
from ecommerce.extensions.payment.constants import STRIPE_CARD_TYPE_MAP
from ecommerce.extensions.payment.processors import (
    ApplePayMixin,
    BaseClientSidePaymentProcessor,
    HandledProcessorResponse
)

logger = logging.getLogger(__name__)

BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
BillingAddress = get_model('order', 'BillingAddress')
Country = get_model('address', 'Country')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class Stripe(ApplePayMixin, BaseClientSidePaymentProcessor):
    NAME = 'stripe'
    template_name = 'payment/stripe.html'

    def __init__(self, site):
        """
        Constructs a new instance of the Stripe processor.

        Raises:
            KeyError: If no settings configured for this payment processor.
        """
        super(Stripe, self).__init__(site)
        configuration = self.configuration

        # Stripe API version to use. Will use latest allowed in Stripe Dashboard if None.
        self.api_version = configuration['api_version']
        # Send anonymous latency metrics to Stripe.
        self.enable_telemetry = configuration['enable_telemetry']
        # Stripe client logging level. None will default to INFO.
        self.log_level = configuration['log_level']
        # How many times to automatically retry requests. None means no retries.
        self.max_network_retries = configuration['max_network_retries']
        # Send requests somewhere else instead of Stripe. May be useful for testing.
        self.proxy = configuration['proxy']
        # The key visible on the frontend to identify our Stripe account. Public.
        self.publishable_key = configuration['publishable_key']
        # The secret API key used by the backend to communicate with Stripe. Private/secret.
        self.secret_key = configuration['secret_key']
        # The webhook endpoint secret used by Stripe to secure the endpoint. Private/secret.
        self.endpoint_secret = configuration['webhook_endpoint_secret']

        stripe.api_key = self.secret_key
        stripe.api_version = self.api_version
        stripe.enable_telemetry = self.enable_telemetry
        stripe.log = self.log_level
        stripe.max_network_retries = self.max_network_retries
        stripe.proxy = self.proxy

    @property
    def cancel_url(self):
        return get_ecommerce_url(self.configuration['cancel_checkout_path'])

    @property
    def error_url(self):
        return get_ecommerce_url(self.configuration['error_path'])

    def _get_basket_amount(self, basket):
        """Convert to stripe amount, which is in cents."""
        return str((basket.total_incl_tax * 100).to_integral_value())

    def _build_payment_intent_parameters(self, basket):
        order_number = basket.order_number
        amount = self._get_basket_amount(basket)
        currency = basket.currency
        return {
            'amount': amount,
            'currency': currency,
            'description': order_number,
            'metadata': {'order_number': order_number},
        }

    def generate_basket_pi_idempotency_key(self, basket):
        """
        Generate an idempotency key for creating a PaymentIntent for a Basket.
        Using a version number in they key to aid in future development.
        """
        return f'basket_pi_create_v1_{basket.order_number}'

    def get_capture_context(self, request):
        # TODO: consider whether the basket should be passed in from MFE, not retrieved from Oscar
        basket = Basket.get_basket(request.user, request.site)
        if not basket.lines.exists():
            logger.info(
                'Stripe capture-context called with empty basket [%d] and order number [%s].',
                basket.id,
                basket.order_number,
            )
            # Create a default stripe_response object with the necessary fields to combat 400 errors
            stripe_response = {
                'id': '',
                'client_secret': '',
            }
        else:
            try:
                logger.info("*** GETTING STRIPE RESPONSE ***")
                stripe_response = stripe.PaymentIntent.create(
                    **self._build_payment_intent_parameters(basket),
                    # This means this payment intent can only be confirmed with secret key (as in, from ecommerce)
                    secret_key_confirmation='required',
                    # don't create a new intent for the same basket
                    idempotency_key=self.generate_basket_pi_idempotency_key(basket),
                )
                logger.info("*** STRIPE RESPONSE %s ***", stripe_response)
                # id is the payment_intent_id from Stripe
                transaction_id = stripe_response['id']

                basket_add_payment_intent_id_attribute(basket, transaction_id)
            # for when basket was already created, but with different amount
            except stripe.error.IdempotencyError:
                # if this PI has been created before, we should be able to retrieve
                # it from Stripe using the payment_intent_id BasketAttribute.
                # Note that we update the PI's price in handle_processor_response
                # before hitting the confirm endpoint, so we don't need to do that here
                payment_intent_id_attribute = BasketAttributeType.objects.get(name=PAYMENT_INTENT_ID_ATTRIBUTE)
                payment_intent_attr = BasketAttribute.objects.get(
                    basket=basket,
                    attribute_type=payment_intent_id_attribute
                )
                transaction_id = payment_intent_attr.value_text.strip()
                logger.info(
                    'Idempotency Error: Retrieving existing Payment Intent for basket [%d]'
                    ' with transaction ID [%s] and order number [%s].',
                    basket.id,
                    transaction_id,
                    basket.order_number,
                )
                stripe_response = stripe.PaymentIntent.retrieve(id=transaction_id)

        new_capture_context = {
            'key_id': stripe_response['client_secret'],
            'order_id': basket.order_number,
        }
        return new_capture_context

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=True, **kwargs):
        return {'payment_page_url': self.client_side_payment_url}

    def handle_processor_response(self, response, basket=None):
        # pretty sure we should simply return/error if basket is None, as not
        # sure what it would mean if there
        payment_intent_id = response['payment_intent_id']
        # NOTE: In the future we may want to get/create a Customer. See https://stripe.com/docs/api#customers.

        # rewrite order amount so it's updated for coupon & quantity and unchanged by the user
        stripe.PaymentIntent.modify(
            payment_intent_id,
            **self._build_payment_intent_parameters(basket),
        )
        try:
            confirm_api_response = stripe.PaymentIntent.confirm(
                payment_intent_id,
                # stop on complicated payments MFE can't handle yet
                error_on_requires_action=True,
                expand=['payment_method'],
            )
        except stripe.error.CardError as err:
            self.record_processor_response(err.json_body, transaction_id=payment_intent_id, basket=basket)
            logger.exception('Card Error for basket [%d]: %s}', basket.id, err)
            raise

        # proceed only if payment went through
        assert confirm_api_response['status'] == "succeeded"
        self.record_processor_response(confirm_api_response, transaction_id=payment_intent_id, basket=basket)

        logger.info(
            'Successfully confirmed Stripe payment intent [%s] for basket [%d] and order number [%s].',
            payment_intent_id,
            basket.id,
            basket.order_number,
        )

        total = basket.total_incl_tax
        currency = basket.currency
        card_object = confirm_api_response['charges']['data'][0]['payment_method_details']['card']
        card_number = card_object['last4']
        card_type = STRIPE_CARD_TYPE_MAP.get(card_object['brand'])

        return HandledProcessorResponse(
            transaction_id=payment_intent_id,
            total=total,
            currency=currency,
            card_number=card_number,
            card_type=card_type
        )

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        try:
            # Stripe requires amount to be in cents. "amount" is a Decimal object to the hundredths place
            amount = int(amount * 100)
            refund = stripe.Refund.create(payment_intent=reference_number, amount=amount)
        except stripe.error.InvalidRequestError as err:
            if err.code == 'charge_already_refunded':
                refund = stripe.Refund.list(payment_intent=reference_number, limit=1)['data'][0]
                self.record_processor_response(refund, transaction_id=refund.id, basket=basket)
                msg = 'Skipping issuing credit (via Stripe) for order [{}] because charge was already refunded.'.format(
                    order_number)
                logger.warning(msg)
            else:
                self.record_processor_response(err.json_body, transaction_id=reference_number, basket=basket)
                msg = 'An error occurred while attempting to issue a credit (via Stripe) for order [{}].'.format(
                    order_number)
                logger.exception(msg)
                raise
        except:
            msg = 'An error occurred while attempting to issue a credit (via Stripe) for order [{}].'.format(
                order_number)
            logger.exception(msg)
            raise GatewayError(msg)  # pylint: disable=raise-missing-from

        transaction_id = refund.id
        self.record_processor_response(refund, transaction_id=transaction_id, basket=basket)

        return transaction_id

    def get_address_from_token(self, payment_intent_id):
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
