"""Test Order Utility classes """
from django.test import TestCase, override_settings

from ecommerce.extensions.order.utils import OrderNumberGenerator
from ecommerce.extensions.test.factories import BasketFactory


class UtilsTest(TestCase):
    """Unit tests for the order utility functions and classes. """

    def test_order_number_generation(self):
        """
        Verify that order numbers are generated correctly, and that they can
        be converted back into basket IDs when necessary.
        """
        first_basket = BasketFactory()
        second_basket = BasketFactory()

        first_order_number = OrderNumberGenerator().order_number(first_basket)
        second_order_number = OrderNumberGenerator().order_number(second_basket)

        # TODO add partner code instead of hard coded value
        partner_code = 'edx'

        self.assertIn(partner_code, first_order_number)
        self.assertIn(partner_code, second_order_number)
        self.assertNotEqual(first_order_number, second_order_number)

        first_basket_id = OrderNumberGenerator().basket_id(first_order_number)
        second_basket_id = OrderNumberGenerator().basket_id(second_order_number)

        self.assertEqual(first_basket_id, first_basket.id)
        self.assertEqual(second_basket_id, second_basket.id)
