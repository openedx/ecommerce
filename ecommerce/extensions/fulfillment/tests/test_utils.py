from __future__ import absolute_import

from decimal import Decimal

from ecommerce.extensions.fulfillment.utils import get_enterprise_customer_cost_for_line
from ecommerce.tests.testcases import TestCase


class UtilTests(TestCase):

    def test_get_enterprise_customer_cost_for_line(self):
        """
        Test correct values for discount percentage are evaluated and rounded.
        """
        list_price = Decimal('199.00')
        effective_discount_percentage = Decimal('0.001027742658353086344768502165')

        actual = get_enterprise_customer_cost_for_line(list_price, effective_discount_percentage)
        expected = Decimal('198.79548')
        self.assertEqual(actual, expected)
