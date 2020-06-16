

import ddt
from django.test import override_settings
from oscar.core.loading import get_model

from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.refund.api import create_refunds, find_orders_associated_with_course
from ecommerce.extensions.refund.tests.factories import RefundLineFactory
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

ProductAttribute = get_model("catalogue", "ProductAttribute")
ProductClass = get_model("catalogue", "ProductClass")
Refund = get_model('refund', 'Refund')

OSCAR_INITIAL_REFUND_STATUS = 'REFUND_OPEN'
OSCAR_INITIAL_REFUND_LINE_STATUS = 'REFUND_LINE_OPEN'


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

        actual = find_orders_associated_with_course(self.user, self.course.id)
        self.assertEqual(actual, [order])

    @ddt.data('', ' ', None)
    def test_find_orders_associated_with_course_invalid_course_id(self, course_id):
        """ ValueError should be raised if course_id is invalid. """
        self.assertRaises(ValueError, find_orders_associated_with_course, self.user, course_id)

    def test_find_orders_associated_with_course_no_orders(self):
        """ An empty list should be returned if the user has never placed an order. """
        self.assertFalse(self.user.orders.exists())

        actual = find_orders_associated_with_course(self.user, self.course.id)
        self.assertEqual(actual, [])

    @ddt.data(ORDER.OPEN, ORDER.FULFILLMENT_ERROR)
    def test_find_orders_associated_with_course_no_completed_orders(self, status):
        """ An empty list should be returned if the user has no completed orders. """
        order = self.create_order()
        order.status = status
        order.save()

        actual = find_orders_associated_with_course(self.user, self.course.id)
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
        actual = create_refunds([order], self.course.id)
        refund = Refund.objects.get(order=order)
        self.assertEqual(actual, [refund])
        self.assert_refund_matches_order(refund, order)

    def test_create_refunds_with_existing_refund(self):
        """ The method should NOT create refunds for lines that have already been refunded. """
        order = self.create_order()
        RefundLineFactory(order_line=order.lines.first())

        actual = create_refunds([order], self.course.id)
        self.assertEqual(actual, [])
