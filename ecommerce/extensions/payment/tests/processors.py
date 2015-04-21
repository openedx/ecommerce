from ecommerce.extensions.payment.processors import BasePaymentProcessor


class DummyProcessor(BasePaymentProcessor):
    NAME = 'dummy'

    def handle_processor_response(self, params):
        pass

    def get_transaction_parameters(self, basket, receipt_page_url=None, cancel_page_url=None,
                                   merchant_defined_data=None):
        pass


class AnotherDummyProcessor(DummyProcessor):
    NAME = 'another-dummy'
