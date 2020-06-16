

from ecommerce.extensions.fulfillment.status import LINE, ORDER
from ecommerce.extensions.test.factories import create_order


class FulfillmentTestMixin:
    """
    Mixin for fulfillment tests.

    Inheriting classes should have a `create_user` method.
    """
    def generate_open_order(self, product_class=None):
        """ Returns an open order, ready to be fulfilled. """
        user = self.create_user()
        return create_order(user=user, status=ORDER.OPEN, product_class=product_class)

    def assert_order_fulfilled(self, order):
        """
        Verifies that an order has been fulfilled.

        An order is considered fulfilled if ALL of the following are true:
            * The order's status is COMPLETE.
            * The order's lines' statuses are COMPLETE.
        """
        self.assertEqual(order.status, ORDER.COMPLETE)
        self.assertSetEqual(set(order.lines.values_list('status', flat=True)), set([LINE.COMPLETE]))
