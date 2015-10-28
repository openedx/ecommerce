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

    def test_unicode(self):
        """ Verify the __unicode__ method returns the correct value. """
        expected = u"{id} - {status} basket (owner: {owner}, lines: {num_lines})".format(
            id=self.basket.id,
            status=self.basket.status,
            owner=self.basket.owner,
            num_lines=self.basket.num_lines)

        self.assertEqual(unicode(self.basket), expected)
