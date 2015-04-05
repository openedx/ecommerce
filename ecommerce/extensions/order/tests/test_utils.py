"""Test Order Utility classes """
from unittest import TestCase
from django.test import override_settings
from oscar.test.newfactories import BasketFactory

from ecommerce.extensions.order.utils import OrderNumberGenerator


class UtilsTest(TestCase):
    """Unit tests for the order utility functions and classes. """

    ORDER_NUMBER_PREFIX = "Zoidberg"

    @override_settings(ORDER_NUMBER_PREFIX=ORDER_NUMBER_PREFIX)
    def create_order_number(self):
        """Test creating order numbers"""
        basket = BasketFactory()
        next_basket = BasketFactory()
        new_order_number = OrderNumberGenerator.order_number(basket)
        next_order_number = OrderNumberGenerator.order_number(next_basket)
        self.assertIn(self.ORDER_NUMBER_PREFIX, new_order_number)
        self.assertIn(self.ORDER_NUMBER_PREFIX, next_order_number)
        self.assertNotEqual(new_order_number, next_order_number)
