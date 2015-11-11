""" Invoice payment processing. """
from oscar.core.loading import get_model

from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.processors import BasePaymentProcessor
from ecommerce.invoice.models import Invoice

PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class InvoicePayment(BasePaymentProcessor):
    """
    Generate an Invoice for the given basket
    """

    NAME = u'invoice'

    def handle_processor_response(self, response, basket=None):
        """
        Since this is an Invoice just record the transaction.

        """

        source_type, __ = SourceType.objects.get_or_create(name=self.NAME)

        source = Source(source_type=source_type, label='Invoice')

        # Create PaymentEvent to track
        event_type, __ = PaymentEventType.objects.get_or_create(
            name=PaymentEventTypeName.PAID)
        event = PaymentEvent(event_type=event_type, processor_name=self.NAME)

        # Create an Invoice.
        Invoice.objects.create(basket=basket)

        return source, event

    def get_transaction_parameters(self, basket, request=None):
        return None

    def issue_credit(self, source, amount, currency):
        raise NotImplementedError
