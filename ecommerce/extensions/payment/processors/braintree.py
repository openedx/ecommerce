import braintree
from oscar.apps.payment.exceptions import GatewayError

from ecommerce.extensions.payment.processors import BasePaymentProcessor, HandledProcessorResponse


class Braintree(BasePaymentProcessor):
    NAME = 'braintree'

    def __init__(self, site):
        """
        Constructs a new instance of the Braintree processor.

        Raises:
            KeyError: If no settings configured for this payment processor
        """

        super(Braintree, self).__init__(site)
        configuration = self.configuration
        self.access_token = configuration['access_token']
        self.gateway = braintree.BraintreeGateway(access_token=self.access_token)

    def generate_client_token(self):
        return self.gateway.client_token.generate()

    def handle_processor_response(self, response, basket=None):
        result = self.gateway.transaction.sale({
            'amount': basket.total_incl_tax,
            'payment_method_nonce': response['payment_method_nonce'],
            'order_id': basket.order_number,
        })
        if result.is_success:
            transaction = result.transaction
            label = None
            card_type = None

            if transaction.payment_instrument_type == 'paypal_account':
                card_type = 'PayPal'
                label = transaction.paypal_details.payer_email

            return HandledProcessorResponse(
                transaction_id=transaction.id,
                total=transaction.amount,
                currency=transaction.currency,
                card_number=label,
                card_type=card_type
            )
        else:
            raise GatewayError(result.message)

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        # TODO Return client token?
        raise NotImplementedError

    def issue_credit(self, order, reference_number, amount, currency):
        result = braintree.Transaction.refund(reference_number, amount=amount)

        basket = order.basket
        if result.is_success:
            transaction = result.transaction
            self.record_processor_response(transaction.to_dict(), transaction_id=transaction.id, basket=basket)
            return transaction.id
        else:
            self.record_processor_response(result.errors.deep_errors, transaction_id=reference_number, basket=basket)
            raise GatewayError(result.errors.deep_errors)
