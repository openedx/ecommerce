import ddt
from django.test import TestCase
from oscar.test import factories

from ecommerce.extensions.fulfillment.status import ORDER


@ddt.ddt
class OrderTests(TestCase):
    def setUp(self):
        super(OrderTests, self).setUp()
        self.order = factories.create_order()

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
