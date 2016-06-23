from __future__ import unicode_literals

from hashlib import md5

from oscar.core.loading import get_model

from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.catalogue.utils import generate_sku
from ecommerce.tests.factories import ProductFactory
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')
Course = get_model('courses', 'Course')
Product = get_model('catalogue', 'Product')

COURSE_ID = 'sku/test_course/course'


class UtilsTests(CourseCatalogTestMixin, TestCase):
    course_id = 'sku/test_course/course'

    def setUp(self):
        super(UtilsTests, self).setUp()
        self.course = Course.objects.create(id=COURSE_ID, name='Test Course')
        self.seat = self.course.create_or_update_seat('verified', False, 0, self.partner)
        self.catalog = Catalog.objects.create(name='Test', partner_id=self.partner.id)

    def test_generate_sku_with_missing_product_class(self):
        """Verify the method raises an exception if the product class is missing."""
        with self.assertRaises(AttributeError):
            generate_sku(Product(), self.partner)

    def test_generate_sku_with_unexpected_product_class(self):
        """Verify the method raises an exception for unsupported product class."""
        product = ProductFactory()
        with self.assertRaises(Exception):
            generate_sku(product, self.partner)

    def test_generate_sku_for_course_seat(self):
        """Verify the method generates a SKU for a course seat."""
        course_id = 'sku/test/course'
        course = Course.objects.create(id=course_id, name='Test Course')
        certificate_type = 'honor'
        product = course.create_or_update_seat(certificate_type, False, 0, self.partner)

        _hash = '{} {} {} {} {}'.format(certificate_type, course_id, 'False', '', self.partner.id)
        _hash = md5(_hash.lower()).hexdigest()[-7:]
        # verify that generated sku has partner 'short_code' as prefix
        expected = _hash.upper()
        actual = generate_sku(product, self.partner)
        self.assertEqual(actual, expected)


class CouponUtilsTests(CouponMixin, CourseCatalogTestMixin, TestCase):
    def setUp(self):
        super(CouponUtilsTests, self).setUp()
        self.course = Course.objects.create(id=COURSE_ID, name='Test Course')
        self.catalog = Catalog.objects.create(name='Test', partner_id=self.partner.id)

    def test_generate_sku_for_coupon(self):
        """Verify the method generates a SKU for a coupon."""
        coupon = self.create_coupon(partner=self.partner)
        _hash = ' '.join((
            unicode(coupon.id),
            str(self.partner.id)
        ))
        digest = md5(_hash.lower()).hexdigest()[-7:]
        expected = digest.upper()
        actual = generate_sku(coupon, self.partner)
        self.assertEqual(actual, expected)
