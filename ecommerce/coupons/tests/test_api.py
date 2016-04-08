# -*- coding: utf-8 -*-

# Framework Libraries
from oscar.core.loading import get_model

# Custom/Extension Libraries
from ecommerce.tests.mixins import CouponMixin
from ecommerce.tests.testcases import TestCase

# Referenced Oscar Models
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


class CouponApiTest(CouponMixin, TestCase):
    """
    Unit tests covering integration scenarios for the Coupons app
    """

    def setUp(self):
        super(CouponApiTest, self).setUp()
        self.product_class, __ = ProductClass.objects.get_or_create(name='Coupon')
        self.coupon = self.create_coupon(
            voucher_type=Voucher.MULTI_USE,
            categories=[self.category]
        )

    def test_create_or_update_coupon_product(self):
        """Test the created coupon data."""
        self.assertEqual(Product.objects.filter(product_class=self.product_class).count(), 1)
        self.assertIsInstance(self.coupon, Product)
        self.assertEqual(self.coupon.title, 'Test CouponMixin Coupon')

        self.assertEqual(StockRecord.objects.filter(product=self.coupon).count(), 1)
        stock_record = StockRecord.objects.get(product=self.coupon)
        self.assertEqual(stock_record.price_currency, 'USD')
        self.assertEqual(stock_record.price_excl_tax, 100)

        self.assertEqual(self.coupon.attr.coupon_vouchers.vouchers.count(), 5)
        category = ProductCategory.objects.get(product=self.coupon).category
        self.assertEqual(category, self.category)
