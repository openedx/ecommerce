# coding=utf-8
from decimal import Decimal

from django.conf import settings
import mock
from mock_django import mock_signal_receiver
from oscar.core.loading import get_model, get_class
from oscar.test.factories import create_order
from oscar.test.newfactories import BasketFactory

from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.refund.status import REFUND, REFUND_LINE
from ecommerce.extensions.refund.tests.factories import CourseFactory, RefundFactory


post_refund = get_class('refund.signals', 'post_refund')
Refund = get_model('refund', 'Refund')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class RefundTestMixin(object):
    def setUp(self):
        self.course_id = u'edX/DemoX/Demo_Course'
        self.course = CourseFactory(self.course_id, u'edX Demó Course')
        self.honor_product = self.course.add_mode('honor', 0)
        self.verified_product = self.course.add_mode('verified', Decimal(10.00), id_verification_required=True)

    def create_order(self, user=None):
        user = user or self.user
        basket = BasketFactory(owner=user)
        basket.add_product(self.verified_product)
        order = create_order(basket=basket, user=user)
        order.status = ORDER.COMPLETE
        order.save()
        return order

    def assert_refund_matches_order(self, refund, order):
        """ Verify the refund corresponds to the given order. """
        self.assertEqual(refund.order, order)
        self.assertEqual(refund.user, order.user)
        self.assertEqual(refund.status, settings.OSCAR_INITIAL_REFUND_STATUS)
        self.assertEqual(refund.total_credit_excl_tax, order.total_excl_tax)
        self.assertEqual(refund.lines.count(), 1)

        refund_line = refund.lines.first()
        line = order.lines.first()
        self.assertEqual(refund_line.status, settings.OSCAR_INITIAL_REFUND_LINE_STATUS)
        self.assertEqual(refund_line.order_line, line)
        self.assertEqual(refund_line.line_credit_excl_tax, line.line_price_excl_tax)
        self.assertEqual(refund_line.quantity, 1)

    def create_refund(self, processor_name='cybersource'):
        refund = RefundFactory()
        order = refund.order
        source_type, __ = SourceType.objects.get_or_create(name=processor_name)
        Source.objects.create(source_type=source_type, order=order, currency=refund.currency,
                              amount_allocated=order.total_incl_tax, amount_debited=order.total_incl_tax)

        return refund

    def approve(self, refund):
        def _revoke_lines(r):
            for line in r.lines.all():
                line.set_status(REFUND_LINE.COMPLETE)

            r.set_status(REFUND.COMPLETE)

        with mock.patch.object(Refund, '_issue_credit', return_value=None):
            with mock.patch.object(Refund, '_revoke_lines', side_effect=_revoke_lines, autospec=True):
                with mock_signal_receiver(post_refund) as receiver:
                    self.assertEqual(receiver.call_count, 0)
                    self.assertTrue(refund.approve())
                    self.assertEqual(receiver.call_count, 1)
