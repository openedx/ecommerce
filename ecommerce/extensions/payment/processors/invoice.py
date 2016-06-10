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
        Record the transaction and store the invoice information in a new Invoice object.
        """
        source_type, __ = SourceType.objects.get_or_create(name=self.NAME)

        source = Source(source_type=source_type, label='Invoice')

        # Create PaymentEvent to track
        event_type, __ = PaymentEventType.objects.get_or_create(
            name=PaymentEventTypeName.PAID)
        event = PaymentEvent(event_type=event_type, processor_name=self.NAME)

        invoice = Invoice.objects.create(order=order, business_client=business_client)
        if invoice_data:
            invoice_type = invoice_data.get('invoice_type')
            invoice.invoice_type = invoice_type
            if invoice_type == 'Prepaid':
                invoice.state = Invoice.PAID
            invoice.number = invoice_data.get('invoice_number')
            invoice.invoiced_amount = invoice_data.get('invoiced_amount')
            invoice.invoice_payment_date = invoice_data.get('invoice_payment_date')
            invoice.tax_deducted_source = True if invoice_data.get('tax_deducted_source') else False
            invoice.invoice_discount_type = invoice_data.get('invoice_discount_type')
            invoice.invoice_discount_value = invoice_data.get('invoice_discount_value')
            invoice.tax_deducted_source = invoice_data.get('tax_deducted_source')
            invoice.tax_deducted_source_value = invoice_data.get('tax_deducted_source_value')
            invoice.save()

        return source, event

    def get_transaction_parameters(self, basket, request=None):
        return None

    def issue_credit(self, source, amount, currency):
        raise NotImplementedError
