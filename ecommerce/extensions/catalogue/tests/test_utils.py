# -*- coding: utf-8 -*-


from hashlib import md5

import ddt
from django.db.utils import IntegrityError
from oscar.core.loading import get_model

from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.catalogue.utils import (
    create_coupon_product,
    create_subcategories,
    generate_sku,
    get_or_create_catalog
)
from ecommerce.tests.factories import ProductFactory
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Category = get_model('catalogue', 'Category')
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')

COURSE_ID = 'sku/test_course/course'
COUPON_CATEGORY_NAME = 'Coupons'


@ddt.ddt
class UtilsTests(DiscoveryTestMixin, TestCase):
    course_id = 'sku/test_course/course'

    def setUp(self):
        super(UtilsTests, self).setUp()
        self.course = CourseFactory(id=COURSE_ID, name='Test Course', partner=self.partner)
        self.seat = self.course.create_or_update_seat('verified', False, 0)
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

    @ddt.data('sku/test/course', 'course-v1:UNCórdobaX+CS001x+3T2017')
    def test_generate_sku_for_course_seat(self, course_id):
        """Verify the method generates a SKU for a course seat."""
        course = CourseFactory(id=course_id, name='Test Course', partner=self.partner)
        certificate_type = 'audit'
        product = course.create_or_update_seat(certificate_type, False, 0)

        _hash = '{} {} {} {} {} {}'.format(certificate_type, course_id, 'False', '', product.id,
                                           self.partner.id).encode('utf-8')
        _hash = md5(_hash.lower()).hexdigest()[-7:]
        # verify that generated sku has partner 'short_code' as prefix
        expected = _hash.upper()
        actual = generate_sku(product, self.partner)
        self.assertEqual(actual, expected)

    def test_get_or_create_catalog(self):
        """Verify that the proper catalog is fetched."""
        stock_record = self.seat.stockrecords.first()
        self.catalog.stock_records.add(stock_record)

        existing_catalog, created = get_or_create_catalog(
            name='Test',
            partner=self.partner,
            stock_record_ids=[stock_record.id]
        )
        self.assertFalse(created)
        self.assertEqual(self.catalog, existing_catalog)
        self.assertEqual(Catalog.objects.count(), 1)

        course_id = 'sku/test2/course'
        course = CourseFactory(id=course_id, name='Test Course 2', partner=self.partner)
        seat_2 = course.create_or_update_seat('verified', False, 0)
        stock_record_2 = seat_2.stockrecords.first()

        new_catalog, created = get_or_create_catalog(
            name='Test',
            partner=self.partner,
            stock_record_ids=[stock_record.id, stock_record_2.id]
        )
        self.assertTrue(created)
        self.assertNotEqual(self.catalog, new_catalog)
        self.assertEqual(Catalog.objects.count(), 2)

    def test_create_subcategories(self):
        """Verify that create_subcategories method is working as per expectations."""
        parent = Category.objects.get(name=COUPON_CATEGORY_NAME)
        existing_children = parent.get_children_count()
        test_categories = ['Test 1', 'Test 2', 'Test 3']

        for category in test_categories:
            assert parent.get_children().filter(name=category).count() == 0

        create_subcategories(Category, COUPON_CATEGORY_NAME, test_categories)

        # Get latest state of parent object from database
        parent.refresh_from_db()
        # Check that number of children for parent is updated after creating subcategories
        assert parent.get_children_count() == existing_children + len(test_categories), \
            "Number of children for parent object isn't updated"

        # Now as we created the sub categories, filter should return that
        for category in test_categories:
            assert parent.get_children().filter(name=category).count() == 1

    def test_create_subcategories_no_category(self):
        """Verify that create_subcategories returns gracefully when model isn't Category"""
        test_categories = ['Test 1', 'Test 2', 'Test 3']
        create_subcategories(Product, COUPON_CATEGORY_NAME, test_categories)


class CouponUtilsTests(CouponMixin, DiscoveryTestMixin, TestCase):
    def setUp(self):
        super(CouponUtilsTests, self).setUp()
        self.course = CourseFactory(id=COURSE_ID, name='Test Course', partner=self.partner)
        self.catalog = Catalog.objects.create(name='Test', partner_id=self.partner.id)

    def test_generate_sku_for_coupon(self):
        """Verify the method generates a SKU for a coupon."""
        coupon = self.create_coupon(partner=self.partner, catalog=self.catalog)
        _hash = ' '.join((
            str(coupon.id),
            str(self.partner.id)
        )).encode('utf-8')

        digest = md5(_hash.lower()).hexdigest()[-7:]
        expected = digest.upper()
        actual = generate_sku(coupon, self.partner)
        self.assertEqual(actual, expected)


class CouponCreationTests(CouponMixin, TestCase):
    def setUp(self):
        super(CouponCreationTests, self).setUp()
        self.catalog = Catalog.objects.create(partner=self.partner)

    def create_custom_coupon(self, benefit_value=100, code='', max_uses=None, note=None, quantity=1,
                             title='Tešt Čoupon', sales_force_id=None, salesforce_opportunity_line_item=None):
        """Create a custom test coupon product."""

        return create_coupon_product(
            benefit_type=Benefit.PERCENTAGE,
            benefit_value=benefit_value,
            catalog=self.catalog,
            catalog_query=None,
            category=self.category,
            code=code,
            course_catalog=None,
            course_seat_types=None,
            email_domains=None,
            end_datetime='2025-1-1',
            enterprise_customer=None,
            enterprise_customer_catalog=None,
            max_uses=max_uses,
            note=note,
            partner=self.partner,
            price=100,
            quantity=quantity,
            start_datetime='2015-1-1',
            title=title,
            voucher_type=Voucher.ONCE_PER_CUSTOMER,
            program_uuid=None,
            site=self.site,
            sales_force_id=sales_force_id,
            salesforce_opportunity_line_item=salesforce_opportunity_line_item
        )

    def test_custom_code_integrity_error(self):
        """Test custom coupon code duplication."""
        self.create_custom_coupon(
            benefit_value=90,
            code='CUSTOMCODE',
            title='Custom coupon',
        )

        with self.assertRaises(IntegrityError):
            self.create_custom_coupon(
                benefit_value=90,
                code='CUSTOMCODE',
                title='Coupon with integrity issue',
            )

    def test_coupon_note(self):
        """Test creating a coupon with a note."""
        note = 'Ñote'
        title = 'Coupon'
        note_coupon = self.create_custom_coupon(note=note, title=title)
        self.assertEqual(note_coupon.attr.note, note)
        self.assertEqual(note_coupon.title, title)

    def test_custom_code_string(self):
        """Test creating a coupon with custom voucher code."""
        custom_code = 'CUSTOMCODE'
        custom_coupon = self.create_custom_coupon(
            benefit_value=90,
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

    def test_coupon_sales_force_id(self):
        """Test creating a coupon with sales force opprtunity id."""
        sales_force_id = 'salesforceid123'
        title = 'Coupon'
        note_coupon = self.create_custom_coupon(sales_force_id=sales_force_id, title=title)
        self.assertEqual(note_coupon.attr.sales_force_id, sales_force_id)
        self.assertEqual(note_coupon.title, title)

    def test_coupon_salesforce_opportunity_line_item(self):
        """Test creating a coupon with sales force opprtunity id."""
        salesforce_opportunity_line_item = 'salesforcelineItem123'
        title = 'Coupon'
        note_coupon = self.create_custom_coupon(
            salesforce_opportunity_line_item=salesforce_opportunity_line_item, title=title)
        self.assertEqual(note_coupon.attr.salesforce_opportunity_line_item, salesforce_opportunity_line_item)
        self.assertEqual(note_coupon.title, title)
