from __future__ import unicode_literals

from hashlib import md5

from oscar.core.loading import get_model

from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.catalogue.utils import generate_sku, get_or_create_catalog, generate_coupon_slug
from ecommerce.extensions.test.factories import create_coupon
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Course = get_model('courses', 'Course')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')

COURSE_ID = 'sku/test_course/course'


class UtilsTests(CourseCatalogTestMixin, TestCase):
    course_id = 'sku/test_course/course'

    def setUp(self):
        super(UtilsTests, self).setUp()
        self.course = Course.objects.create(id=COURSE_ID, name='Test Course')
        self.course.create_or_update_seat('verified', False, 0, self.partner)
        self.catalog = Catalog.objects.create(name='Test', partner_id=self.partner.id)

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
        self.catalog.stock_records.add(StockRecord.objects.get(id=1))

        self.assertEqual(self.catalog.id, 1)

        existing_catalog, created = get_or_create_catalog(
            name='Test',
            partner=self.partner,
            stock_record_ids=[1]
        )
        self.assertFalse(created)
        self.assertEqual(self.catalog, existing_catalog)
        self.assertEqual(Catalog.objects.count(), 1)

        course_id = 'sku/test2/course'
        course = Course.objects.create(id=course_id, name='Test Course 2')
        course.create_or_update_seat('verified', False, 0, self.partner)

        new_catalog, created = get_or_create_catalog(
            name='Test',
            partner=self.partner,
            stock_record_ids=[1, 2]
        )
        self.assertTrue(created)
        self.assertNotEqual(self.catalog, new_catalog)
        self.assertEqual(Catalog.objects.count(), 2)

    def test_generate_coupon_slug(self):
        """Verify the method generates proper slug."""
        title = 'Test coupon'
        _hash = ' '.join((
            unicode(title),
            unicode(self.catalog.id),
            str(self.partner.id)
        ))
        _hash = md5(_hash.lower()).hexdigest()[-10:]
        expected = _hash.upper()
        actual = generate_coupon_slug(self.partner, title=title, catalog=self.catalog)
        self.assertEqual(actual, expected)


class CouponUtilsTests(TestCase):

    def setUp(self):
        super(CouponUtilsTests, self).setUp()
        self.course = Course.objects.create(id=COURSE_ID, name='Test Course')
        self.catalog = Catalog.objects.create(name='Test', partner_id=self.partner.id)

    def test_generate_sku_for_coupon(self):
        """Verify the method generates a SKU for a coupon."""
        coupon = create_coupon(partner=self.partner, catalog=self.catalog)
        _hash = ' '.join((
            unicode(coupon.id),
            unicode(self.catalog.id),
            str(self.partner.id)
        ))
        digest = md5(_hash.lower()).hexdigest()[-7:]
        expected = digest.upper()
        actual = generate_sku(coupon, self.partner, catalog=self.catalog)
        self.assertEqual(actual, expected)
