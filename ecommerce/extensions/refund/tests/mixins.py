from oscar.core.loading import get_model

from ecommerce.extensions.refund.tests.factories import RefundFactory

Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class RefundTestMixin(object):
    def create_refund(self, processor_name='cybersource'):
        refund = RefundFactory()
        order = refund.order
        source_type, __ = SourceType.objects.get_or_create(name=processor_name)
        Source.objects.create(source_type=source_type, order=order, currency=refund.currency,
                              amount_allocated=order.total_incl_tax, amount_debited=order.total_incl_tax)

        return refund
