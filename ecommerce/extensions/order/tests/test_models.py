

import ddt
from oscar.test import factories

from ecommerce.core.constants import COUPON_PRODUCT_CLASS_NAME
from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.test.factories import create_basket, create_order
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class OrderTests(TestCase):
    def setUp(self):
        super(OrderTests, self).setUp()
        self.order = create_order()

    @ddt.data(ORDER.OPEN, ORDER.FULFILLMENT_ERROR)
    def test_is_fulfillable(self, status):
        """
        Order.is_fulfillable should return True if the order's status is
        ORDER.OPEN or ORDER.FULFILLMENT_ERROR.
        """
        self.order.status = status
        self.order.save()
        self.assertTrue(self.order.is_fulfillable)

    @ddt.data(ORDER.COMPLETE)
    def test_is_not_fulfillable(self, status):
        """Order.is_fulfillable should return False if the order's status is ORDER.COMPLETE."""
        self.order.status = status
        self.order.save()
        self.assertFalse(self.order.is_fulfillable)

    def test_contains_coupon(self):
        self.assertFalse(self.order.contains_coupon)

        product = factories.create_product(product_class=COUPON_PRODUCT_CLASS_NAME)
        basket = create_basket(empty=True)
        factories.create_stockrecord(product, num_in_stock=1)
        basket.add_product(product)
        order = create_order(basket=basket)
        self.assertTrue(order.contains_coupon)
