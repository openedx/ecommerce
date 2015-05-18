# coding=utf-8
from decimal import Decimal
from unittest import TestCase

import ddt
from django.conf import settings
from django.test import override_settings
from oscar.core.loading import get_model
from oscar.test.factories import create_order
from oscar.test.newfactories import UserFactory, BasketFactory

from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.refund.api import find_orders_associated_with_course, create_refunds
from ecommerce.extensions.refund.tests.factories import CourseFactory, RefundLineFactory

ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")
Refund = get_model('refund', 'Refund')

OSCAR_INITIAL_REFUND_STATUS = 'REFUND_OPEN'
OSCAR_INITIAL_REFUND_LINE_STATUS = 'REFUND_LINE_OPEN'


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


@ddt.ddt
class ApiTests(RefundTestMixin, TestCase):
    def setUp(self):
        super(ApiTests, self).setUp()
        self.user = UserFactory()

    def test_find_orders_associated_with_course(self):
        """
        Ideal scenario: user has completed orders related to the course, and the verification close date has not passed.
        """
        order = self.create_order()
        self.assertTrue(self.user.orders.exists())

        actual = find_orders_associated_with_course(self.user, self.course_id)
        self.assertEqual(actual, [order])

    @ddt.data('', ' ', None)
    def test_find_orders_associated_with_course_invalid_course_id(self, course_id):
        """ ValueError should be raised if course_id is invalid. """
        self.assertRaises(ValueError, find_orders_associated_with_course, self.user, course_id)

    def test_find_orders_associated_with_course_no_orders(self):
        """ An empty list should be returned if the user has never placed an order. """
        self.assertFalse(self.user.orders.exists())

        actual = find_orders_associated_with_course(self.user, self.course_id)
        self.assertEqual(actual, [])

    @ddt.data(ORDER.OPEN, ORDER.FULFILLMENT_ERROR)
    def test_find_orders_associated_with_course_no_completed_orders(self, status):
        """ An empty list should be returned if the user has no completed orders. """
        order = self.create_order()
        order.status = status
        order.save()

        actual = find_orders_associated_with_course(self.user, self.course_id)
        self.assertEqual(actual, [])

    # TODO Implement this when we begin storing the verification close date.
    # def test_create_refunds_verification_closed(self):
    #     """ No refunds should be created if the verification close date has passed. """
    #     self.fail()

    @override_settings(OSCAR_INITIAL_REFUND_STATUS=OSCAR_INITIAL_REFUND_STATUS,
                       OSCAR_INITIAL_REFUND_LINE_STATUS=OSCAR_INITIAL_REFUND_LINE_STATUS)
    def test_create_refunds(self):
        """ The method should create refunds for orders/lines that have not been refunded. """
        order = self.create_order()
        actual = create_refunds([order], self.course_id)
        refund = Refund.objects.get(order=order)
        self.assertEqual(actual, [refund])
        self.assert_refund_matches_order(refund, order)

    def test_create_refunds_with_existing_refund(self):
        """ The method should NOT create refunds for lines that have already been refunded. """
        order = self.create_order()
        RefundLineFactory(order_line=order.lines.first())

        actual = create_refunds([order], self.course_id)
        self.assertEqual(actual, [])
