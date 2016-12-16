# coding=utf-8

from django.conf import settings
from django.test import override_settings
import mock
from mock_django import mock_signal_receiver
from oscar.core.loading import get_model, get_class
from oscar.test.factories import create_order
from oscar.test.newfactories import BasketFactory

from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.payment.tests.processors import DummyProcessor
from ecommerce.extensions.refund.status import REFUND, REFUND_LINE
from ecommerce.extensions.refund.tests.factories import RefundFactory

post_refund = get_class('refund.signals', 'post_refund')
Refund = get_model('refund', 'Refund')
Source = get_model('payment', 'Source')
SourceType = get_model('payment', 'SourceType')


class RefundTestMixin(CourseCatalogTestMixin):
    def setUp(self):
        super(RefundTestMixin, self).setUp()
        self.course, __ = Course.objects.get_or_create(id=u'edX/DemoX/Demo_Course', name=u'edX Demó Course')
        self.honor_product = self.course.create_or_update_seat('honor', False, 0, self.partner)
        self.verified_product = self.course.create_or_update_seat('verified', True, 10, self.partner)
        self.credit_product = self.course.create_or_update_seat(
            'credit',
            True,
            100,
            self.partner,
            credit_provider='HGW'
        )

    def create_order(self, user=None, credit=False, multiple_lines=False, free=False, status=ORDER.COMPLETE):
        user = user or self.user
        basket = BasketFactory(owner=user)

        if credit:
            basket.add_product(self.credit_product)
        elif multiple_lines:
            basket.add_product(self.verified_product)
            basket.add_product(self.honor_product)
        elif free:
            basket.add_product(self.honor_product)
        else:
            basket.add_product(self.verified_product)

        order = create_order(basket=basket, user=user)
        order.status = status
        order.save()
        return order

    def assert_refund_matches_order(self, refund, order):
        """ Verify the refund corresponds to the given order. """
        self.assertEqual(refund.order, order)
        self.assertEqual(refund.user, order.user)
        self.assertEqual(refund.status, settings.OSCAR_INITIAL_REFUND_STATUS)
        self.assertEqual(refund.total_credit_excl_tax, order.total_excl_tax)
        self.assertEqual(refund.lines.count(), order.lines.count())

        refund_lines = refund.lines.all()
        order_lines = order.lines.all().order_by('refund_lines')
        for refund_line, order_line in zip(refund_lines, order_lines):
            self.assertEqual(refund_line.status, settings.OSCAR_INITIAL_REFUND_LINE_STATUS)
            self.assertEqual(refund_line.order_line, order_line)
            self.assertEqual(refund_line.line_credit_excl_tax, order_line.line_price_excl_tax)
            self.assertEqual(refund_line.quantity, order_line.quantity)

    def create_refund(self, processor_name=DummyProcessor.NAME):
        refund = RefundFactory()
        order = refund.order
        source_type, __ = SourceType.objects.get_or_create(name=processor_name)
        Source.objects.create(source_type=source_type, order=order, currency=refund.currency,
                              amount_allocated=order.total_incl_tax, amount_debited=order.total_incl_tax)

        return refund

    @override_settings(PAYMENT_PROCESSORS=['ecommerce.extensions.payment.tests.processors.DummyProcessor'])
    def approve(self, refund):
        def _revoke_lines(r):
            for line in r.lines.all():
                line.set_status(REFUND_LINE.COMPLETE)

            r.set_status(REFUND.COMPLETE)

        with mock.patch.object(Refund, '_revoke_lines', side_effect=_revoke_lines, autospec=True):
            with mock_signal_receiver(post_refund) as receiver:
                self.assertEqual(receiver.call_count, 0)
                self.assertTrue(refund.approve())
                self.assertEqual(receiver.call_count, 1)
