import ddt
from django.test import TestCase

from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.extensions.test import factories


@ddt.ddt
class OrderTests(TestCase):
    def setUp(self):
        super(OrderTests, self).setUp()
        self.order = factories.create_order()

    def test_can_retry_fulfillment_with_fulfillment_error(self):
        """ Order.can_retry_fulfillment should return True if the order's status is ORDER.FULFILLMENT_ERROR. """
        self.order.status = ORDER.FULFILLMENT_ERROR
        self.order.save()
        self.assertTrue(self.order.can_retry_fulfillment)

    @ddt.data(ORDER.OPEN)
    def test_can_retry_fulfillment_without_fulfillment_error(self, status):
        """ Order.can_retry_fulfillment should return False if the order's status is *not* ORDER.FULFILLMENT_ERROR. """
        self.order.status = status
        self.order.save()
        self.assertFalse(self.order.can_retry_fulfillment)
