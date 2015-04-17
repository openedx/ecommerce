from ecommerce.extensions.payment.processors import BasePaymentProcessor


class DummyProcessor(BasePaymentProcessor):
    NAME = 'dummy'

    def handle_processor_response(self, response, basket=None):
        pass

    def get_transaction_parameters(self, basket, receipt_page_url=None, cancel_page_url=None, **kwargs):
        pass

    def is_signature_valid(self, response):
        pass


class AnotherDummyProcessor(DummyProcessor):
    NAME = 'another-dummy'
