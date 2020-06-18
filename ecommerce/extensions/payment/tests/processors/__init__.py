

from ecommerce.extensions.payment.processors import BaseClientSidePaymentProcessor, HandledProcessorResponse


class DummyProcessor(BaseClientSidePaymentProcessor):
    NAME = 'dummy'
    REFUND_TRANSACTION_ID = 'fake-refund'

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        """ Get the transaction parameters for the processor. """

    def handle_processor_response(self, response, basket=None):
        return HandledProcessorResponse(
            transaction_id=basket.id,
            total=basket.total_incl_tax,
            currency=basket.currency,
            card_number=basket.owner.username,
            card_type='Visa'
        )

    def is_signature_valid(self, response):
        """ Checks if transaction signature is valid. """

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        return self.REFUND_TRANSACTION_ID


class AnotherDummyProcessor(DummyProcessor):
    NAME = 'another-dummy'
