# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from hashlib import md5

from django.db.utils import IntegrityError
from oscar.core.loading import get_model

from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.catalogue.utils import create_coupon_product, generate_sku, get_or_create_catalog
from ecommerce.tests.factories import ProductFactory
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Course = get_model('courses', 'Course')
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')

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

    def test_get_or_create_catalog(self):
        """Verify that the proper catalog is fetched."""
        stock_record = self.seat.stockrecords.first()
        self.catalog.stock_records.add(stock_record)

        self.assertEqual(self.catalog.id, 1)

        existing_catalog, created = get_or_create_catalog(
            name='Test',
            partner=self.partner,
            stock_record_ids=[stock_record.id]
        )
        self.assertFalse(created)
        self.assertEqual(self.catalog, existing_catalog)
        self.assertEqual(Catalog.objects.count(), 1)

        course_id = 'sku/test2/course'
        course = Course.objects.create(id=course_id, name='Test Course 2')
        seat_2 = course.create_or_update_seat('verified', False, 0, self.partner)
        stock_record_2 = seat_2.stockrecords.first()

        new_catalog, created = get_or_create_catalog(
            name='Test',
            partner=self.partner,
            stock_record_ids=[stock_record.id, stock_record_2.id]
        )
        self.assertTrue(created)
        self.assertNotEqual(self.catalog, new_catalog)
        self.assertEqual(Catalog.objects.count(), 2)


class CouponUtilsTests(CouponMixin, CourseCatalogTestMixin, TestCase):
    def setUp(self):
        super(CouponUtilsTests, self).setUp()
        self.course = Course.objects.create(id=COURSE_ID, name='Test Course')
        self.catalog = Catalog.objects.create(name='Test', partner_id=self.partner.id)

    def test_generate_sku_for_coupon(self):
        """Verify the method generates a SKU for a coupon."""
        coupon = self.create_coupon(partner=self.partner, catalog=self.catalog)
        _hash = ' '.join((
            unicode(coupon.id),
            str(self.partner.id)
        ))
        digest = md5(_hash.lower()).hexdigest()[-7:]
        expected = digest.upper()
        actual = generate_sku(coupon, self.partner)
        self.assertEqual(actual, expected)


class CouponCreationTests(CouponMixin, TestCase):
    def setUp(self):
        super(CouponCreationTests, self).setUp()
        self.catalog = Catalog.objects.create(partner=self.partner)

    def create_custom_coupon(self, code='', max_uses=None, note=None, quantity=1, title='Tešt Čoupon'):
        """Create a custom test coupon product."""

        return create_coupon_product(
            benefit_type=Benefit.PERCENTAGE,
            benefit_value=100,
            catalog=self.catalog,
            catalog_query=None,
            category=self.category,
            code=code,
            course_seat_types=None,
            end_datetime='2020-1-1',
            max_uses=max_uses,
            note=note,
            partner=self.partner,
            price=100,
            quantity=quantity,
            start_datetime='2015-1-1',
            title=title,
            voucher_type=Voucher.ONCE_PER_CUSTOMER,
        )

    def test_custom_code_integrity_error(self):
        """Test custom coupon code duplication."""
        self.create_custom_coupon(
            code='CUSTOMCODE',
            title='Custom coupon',
        )

        with self.assertRaises(IntegrityError):
            self.create_custom_coupon(
                code='CUSTOMCODE',
                title='Coupon with integrity issue',
            )

    def test_coupon_note(self):
        """Test creating a coupon with a note."""
        note_coupon = self.create_custom_coupon(
            note='𝑵𝑶𝑻𝑬',
            title='Coupon',
        )
        self.assertEqual(note_coupon.attr.note, '𝑵𝑶𝑻𝑬')
        self.assertEqual(note_coupon.title, 'Coupon')

    def test_custom_code_string(self):
        """Test creating a coupon with custom voucher code."""
        custom_code = 'ČUSTOMĆODE'
        custom_coupon = self.create_custom_coupon(
            code=custom_code,
            quantity=1,
            title='Custom coupon',
        )
        self.assertEqual(custom_coupon.attr.coupon_vouchers.vouchers.count(), 1)
        self.assertEqual(custom_coupon.attr.coupon_vouchers.vouchers.first().code, custom_code)

    def test_multi_use_coupon_creation(self):
        """Test that the endpoint supports the creation of multi-usage coupons."""
        max_uses_number = 2
        coupon = self.create_custom_coupon(max_uses=max_uses_number)
        voucher = coupon.attr.coupon_vouchers.vouchers.first()
        self.assertEqual(voucher.offers.first().max_global_applications, max_uses_number)
