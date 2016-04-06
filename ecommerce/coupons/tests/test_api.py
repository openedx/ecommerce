# -*- coding: utf-8 -*-

# Framework Libraries
from oscar.core.loading import get_model

# Custom/Extension Libraries
from ecommerce.courses.tests.factories import CourseFactory
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
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        course = CourseFactory(id='edx/Demo_Course/DemoX')
        course.create_or_update_seat('verified', True, 50, self.partner)

        self.catalog = Catalog.objects.create(partner=self.partner)
        self.product_class, __ = ProductClass.objects.get_or_create(name='Coupon')
        self.coupon_data = {
            'partner': self.partner,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'catalog': self.catalog,
            'end_date': '2020-1-1',
            'code': '',
            'quantity': 2,
            'start_date': '2015-1-1',
            'voucher_type': Voucher.MULTI_USE,
            'categories': [self.category],
            'note': None,
        }

    def test_create_coupon_product(self):
        """Test the created coupon data."""
        coupon = self.create_coupon()
        self.assertEqual(Product.objects.filter(product_class=self.product_class).count(), 1)
        self.assertIsInstance(coupon, Product)
        self.assertEqual(coupon.title, 'Test coupon')

        self.assertEqual(StockRecord.objects.filter(product=coupon).count(), 1)
        stock_record = StockRecord.objects.get(product=coupon)
        self.assertEqual(stock_record.price_currency, 'USD')
        self.assertEqual(stock_record.price_excl_tax, 100)

        self.assertEqual(coupon.attr.coupon_vouchers.vouchers.count(), 5)
        category = ProductCategory.objects.get(product=coupon).category
        self.assertEqual(category, self.category)
