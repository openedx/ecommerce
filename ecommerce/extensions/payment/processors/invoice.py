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

    def handle_processor_response(
            self, response, order=None, business_client=None, invoice_data=None
    ):  # pylint: disable=arguments-differ
        """
        Create a new invoice record and return the source and event.
        """

        source_type, __ = SourceType.objects.get_or_create(name=self.NAME)
        source = Source(source_type=source_type, label='Invoice')

        event_type, __ = PaymentEventType.objects.get_or_create(
            name=PaymentEventTypeName.PAID)
        event = PaymentEvent(event_type=event_type, processor_name=self.NAME)

        invoice = Invoice.objects.create(order=order, business_client=business_client)
        if invoice_data:
            invoice.number = invoice_data.get('number')
            invoice.type = invoice_data.get('type')
            invoice.payment_date = invoice_data.get('payment_date')
            invoice.discount_type = invoice_data.get('discount_type')
            invoice.discount_value = invoice_data.get('discount_value')
            invoice.tax_deducted_source = invoice_data.get('tax_deducted_source')
            invoice.save()
        return source, event

    def get_transaction_parameters(self, basket, request=None, use_client_side_checkout=False, **kwargs):
        return None

    def issue_credit(self, order_number, basket, reference_number, amount, currency):
        raise NotImplementedError
