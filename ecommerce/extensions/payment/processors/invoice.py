""" Invoice payment processing. """
from decimal import Decimal

from django.conf import settings
from oscar.core.loading import get_model

from ecommerce.invoice.models import Invoice
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.processors import BasePaymentProcessor


PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class InvoicePayment(BasePaymentProcessor):
    """
    Generate an Invoice for the given order
    """

    NAME = u'invoice'

    def __init__(self):
        """
        Constructs a new instance of the Invoice processor.

        """
        configuration = self.configuration
        self.receipt_url = configuration['receipt_url']
        self.error_url = configuration['error_url']
        self.cancel_url = configuration['cancel_url']
        self.language_code = settings.LANGUAGE_CODE

    def handle_processor_response(self, response, basket=None):
        """
        Since this is an Invoice just record the transaction.

        """

        source_type, __ = SourceType.objects.get_or_create(name=self.NAME)
        currency = response[u'req_currency']
        total = Decimal(response[u'req_amount'])
        transaction_id = response[u'transaction_id']
        req_card_number = 'Invoice'
        card_type = 'Invoice'

        source = Source(source_type=source_type,
                        currency=currency,
                        amount_allocated=total,
                        amount_debited=total,
                        reference=transaction_id,
                        label=req_card_number,
                        card_type=card_type)

        # Create PaymentEvent to track
        event_type, __ = PaymentEventType.objects.get_or_create(
            name=PaymentEventTypeName.PAID)
        event = PaymentEvent(event_type=event_type, amount=total,
                             reference=transaction_id, processor_name=self.NAME)

        """
        Create an Invoice.
        """
        invoice = Invoice()
        invoice.invoice_number = transaction_id
        invoice.client = basket.lines.first().product.attr.client
        invoice.order_number = basket.order_number
        invoice.total = total
        invoice.save()

        return source, event

    def get_transaction_parameters(self, basket, request=None):
        return None

    def issue_credit(self, source, amount, currency):
        order = source.order

        return order
