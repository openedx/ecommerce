from django.core.management import call_command
from oscar.core.loading import get_model

from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.tests.testcases import TestCase

Category = get_model('catalogue', 'Category')
ProductCategory = get_model('catalogue', 'ProductCategory')


class TestCouponCommand(CouponMixin, TestCase):
    """ Test coupon populate_coupon_category command. """
    def setUp(self):
        super(TestCouponCommand, self).setUp()
        self.filler_category, __ = Category.objects.get_or_create(name='Support-Other', defaults={'depth': 1})
        self.coupon = self.create_coupon()

    def test_add_category_to_coupon(self):
        """ Verify the correct category is assigned to a coupon without category. """
        ProductCategory.objects.filter(product=self.coupon).delete()
        self.assertEqual(ProductCategory.objects.count(), 0)

        call_command('populate_coupon_categories')
        self.assertEqual(ProductCategory.objects.count(), 1)
        self.assertEqual(ProductCategory.objects.get(product=self.coupon).category, self.filler_category)

    def test_coupon_with_category_unaffected(self):
        """ Verify coupon with category is unchanged after running command. """
        self.assertEqual(ProductCategory.objects.count(), 1)
        category = ProductCategory.objects.get(product=self.coupon).category

        call_command('populate_coupon_categories')
        self.assertEqual(ProductCategory.objects.count(), 1)
        self.assertEqual(ProductCategory.objects.get(product=self.coupon).category, category)
