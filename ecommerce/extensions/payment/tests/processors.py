from ecommerce.extensions.payment.processors import BasePaymentProcessor


class DummyProcessor(BasePaymentProcessor):
    NAME = 'dummy'

    def get_transaction_parameters(self, basket):
        pass

    def handle_processor_response(self, response, basket=None):
        pass

    def is_signature_valid(self, response):
        pass


class AnotherDummyProcessor(DummyProcessor):
    NAME = 'another-dummy'
