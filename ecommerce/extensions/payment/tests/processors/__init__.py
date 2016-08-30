from ecommerce.extensions.payment.processors.base import BasePaymentProcessor


class DummyProcessor(BasePaymentProcessor):
    NAME = 'dummy'

    def get_transaction_parameters(self, basket, request=None):
        pass

    def handle_payment_authorization_response(self, response, basket=None):
        pass

    def is_signature_valid(self, response):
        pass

    def issue_credit(self, transaction_id, amount, currency):
        pass


class AnotherDummyProcessor(DummyProcessor):
    NAME = 'another-dummy'
