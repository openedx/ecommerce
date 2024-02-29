from ecommerce.extensions.iap.utils import get_consumable_android_sku
from ecommerce.tests.testcases import TestCase


class ConsumableAndroidSkuTests(TestCase):
    expected_sku = 'mobile.android.usd49'

    def test_decimal_price(self):
        sku = get_consumable_android_sku(49.50)
        self.assertEqual(sku, self.expected_sku)

    def test_integer_price(self):
        sku = get_consumable_android_sku(49)
        self.assertEqual(sku, self.expected_sku)
