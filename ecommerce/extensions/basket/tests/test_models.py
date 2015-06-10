from django.test import TestCase
from oscar.core.loading import get_class
from oscar.test import factories


OrderNumberGenerator = get_class('order.utils', 'OrderNumberGenerator')


class BasketTests(TestCase):
    def setUp(self):
        super(BasketTests, self).setUp()
        self.basket = factories.create_basket()

    def test_order_number_generation(self):
        """Verify that an instance of Basket can generate its own order number."""
        expected = OrderNumberGenerator().order_number(self.basket)
        self.assertEqual(self.basket.order_number, expected)
