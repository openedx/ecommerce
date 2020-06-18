""" Stripe payment processing. """


import logging

import stripe
from oscar.apps.payment.exceptions import GatewayError, TransactionDeclined
from oscar.core.loading import get_model

from ecommerce.extensions.payment.constants import STRIPE_CARD_TYPE_MAP
from ecommerce.extensions.payment.processors import (
    ApplePayMixin,
    BaseClientSidePaymentProcessor,
    HandledProcessorResponse
)

logger = logging.getLogger(__name__)

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
        self.publishable_key = configuration['publishable_key']
        self.secret_key = configuration['secret_key']
        self.country = configuration['country']

        stripe.api_key = self.secret_key

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=True, **kwargs):
        raise NotImplementedError('The Stripe payment processor does not support transaction parameters.')

    def _get_basket_amount(self, basket):
        return str((basket.total_incl_tax * 100).to_integral_value())

    def handle_processor_response(self, response, basket=None):
        token = response
        order_number = basket.order_number
        currency = basket.currency

        # NOTE: In the future we may want to get/create a Customer. See https://stripe.com/docs/api#customers.
        try:
            charge = stripe.Charge.create(
                amount=self._get_basket_amount(basket),
                currency=currency,
                source=token,
                description=order_number,
                metadata={'order_number': order_number}
            )
            transaction_id = charge.id

            # NOTE: Charge objects subclass the dict class so there is no need to do any data transformation
            # before storing the response in the database.
            self.record_processor_response(charge, transaction_id=transaction_id, basket=basket)
            logger.info('Successfully created Stripe charge [%s] for basket [%d].', transaction_id, basket.id)
        except stripe.error.CardError as ex:
            base_message = "Stripe payment for basket [%d] declined with HTTP status [%d]"
            exception_format_string = "{}: %s".format(base_message)
            body = ex.json_body
            logger.exception(
                exception_format_string,
                basket.id,
                ex.http_status,
                body
            )
            self.record_processor_response(body, basket=basket)
            raise TransactionDeclined(base_message, basket.id, ex.http_status)

        total = basket.total_incl_tax
        card_number = charge.source.last4
        card_type = STRIPE_CARD_TYPE_MAP.get(charge.source.brand)

        return HandledProcessorResponse(
            transaction_id=transaction_id,
            total=total,
            currency=currency,
            card_number=card_number,
            card_type=card_type
        )

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        try:
            refund = stripe.Refund.create(charge=reference_number)
        except:
            msg = 'An error occurred while attempting to issue a credit (via Stripe) for order [{}].'.format(
                order_number)
            logger.exception(msg)
            raise GatewayError(msg)

        transaction_id = refund.id

        # NOTE: Refund objects subclass dict so there is no need to do any data transformation
        # before storing the response in the database.
        self.record_processor_response(refund, transaction_id=transaction_id, basket=basket)

        return transaction_id

    def get_address_from_token(self, token):
        """ Retrieves the billing address associated with token.

        Returns:
            BillingAddress
        """
        data = stripe.Token.retrieve(token)['card']
        address = BillingAddress(
            first_name=data['name'],    # Stripe only has a single name field
            last_name='',
            line1=data['address_line1'],
            line2=data.get('address_line2') or '',
            line4=data['address_city'],  # Oscar uses line4 for city
            postcode=data.get('address_zip') or '',
            state=data.get('address_state') or '',
            country=Country.objects.get(iso_3166_1_a2__iexact=data['address_country'])
        )
        return address
