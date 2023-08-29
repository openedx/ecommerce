

import ddt
from django.core.exceptions import ValidationError
from django.utils.timezone import now, timedelta
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
ProductClass = get_model('catalogue', 'ProductClass')


@ddt.ddt
class ProductTests(CouponMixin, DiscoveryTestMixin, TestCase):
    COUPON_PRODUCT_TITLE = 'Some test title.'

    def _create_coupon_product_with_attributes(
            self, note='note', notify_email=None, sales_force_id=None, salesforce_opportunity_line_item=None):
        """Helper method that creates a coupon product with note, notify_email and sales_force_id attributes."""
        coupon_product = factories.ProductFactory(
            title=self.COUPON_PRODUCT_TITLE,
            product_class=self.coupon_product_class,
            categories=[]
        )
        voucher = factories.VoucherFactory()
        coupon_vouchers = CouponVouchers.objects.create(coupon=coupon_product)
        coupon_vouchers.vouchers.add(voucher)
        coupon_product.attr.coupon_vouchers = coupon_vouchers
        coupon_product.attr.note = note
        if notify_email:
            coupon_product.attr.notify_email = notify_email
        if sales_force_id:
            coupon_product.attr.sales_force_id = sales_force_id
        if salesforce_opportunity_line_item:
            coupon_product.attr.salesforce_opportunity_line_item = salesforce_opportunity_line_item
        coupon_product.save()
        return coupon_product

    def update_product_expires(self, product):
        expiration_datetime = now()
        product.expires = expiration_datetime
        product.save()
        return expiration_datetime

    def test_seat_expires_update(self):
        """Verify updating a seat's expiration date updates enrollment code's."""
        __, seat, enrollment_code = self.create_course_seat_and_enrollment_code()
        self.assertEqual(seat.expires, enrollment_code.expires)

        expiration_datetime = self.update_product_expires(seat)
        enrollment_code.refresh_from_db()
        self.assertEqual(enrollment_code.expires, expiration_datetime)

    def test_enrollment_code_expires_update(self):
        """Verify updating enrollment code's expiration date does not update seat's."""
        __, seat, enrollment_code = self.create_course_seat_and_enrollment_code()
        self.assertEqual(seat.expires, enrollment_code.expires)

        expiration_datetime = self.update_product_expires(enrollment_code)
        seat.refresh_from_db()
        self.assertNotEqual(seat.expires, expiration_datetime)

    def mock_enrollment_code_deactivation(self, enrollment_code):
        enrollment_code.expires = now() - timedelta(days=1)
        enrollment_code.save()

    def test_deactivated_enrollment_code_update(self):
        """Verify a deactivated enrollment code's expiration date is not updated."""
        __, seat, enrollment_code = self.create_course_seat_and_enrollment_code()
        self.assertEqual(seat.expires, enrollment_code.expires)

        self.mock_enrollment_code_deactivation(enrollment_code)
        expiration_datetime = self.update_product_expires(seat)
        enrollment_code.refresh_from_db()
        self.assertNotEqual(enrollment_code.expires, expiration_datetime)

    def test_create_product_with_note(self):
        """Verify creating a product with valid note value creates product."""
        note = 'Some test note.'
        coupon = self._create_coupon_product_with_attributes(note)
        self.assertEqual(coupon.attr.note, note)

    def test_create_product_with_sales_force_id(self):
        """Verify creating a product with sales_force_id."""
        sales_force_id = 'salesforceid123'
        coupon = self._create_coupon_product_with_attributes(sales_force_id=sales_force_id)
        self.assertEqual(coupon.attr.sales_force_id, sales_force_id)

    def test_create_product_with_salesforce_opportunity_line_item(self):
        """Verify creating a product with salesforce_opportunity_line_item."""
        salesforce_opportunity_line_item = 'salesforceopportunitylineitem123'
        coupon = self._create_coupon_product_with_attributes(
            salesforce_opportunity_line_item=salesforce_opportunity_line_item)
        self.assertEqual(coupon.attr.salesforce_opportunity_line_item, salesforce_opportunity_line_item)

    @ddt.data(1, {'some': 'dict'}, ['array'])
    def test_incorrect_note_value_raises_exception(self, note):
        """Verify creating product with invalid note type raises ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_coupon_product_with_attributes(note)

    def test_create_product_with_correct_notify_email(self):
        """
        Verify creating a product with valid notify_email value creates product.
        """
        notify_email = 'batman@gotham.comics'
        coupon_product = self._create_coupon_product_with_attributes(notify_email=notify_email)
        self.assertEqual(coupon_product.attr.notify_email, notify_email)

    @ddt.data('batman', {'some': 'dict'}, ['array'])
    def test_create_product_with_incorrect_notify_email(self, notify_email):
        """
        Verify creating product with invalid notify_email type raises ValidationError.
        """
        with self.assertRaises(ValidationError) as ve:
            self._create_coupon_product_with_attributes(notify_email=notify_email)

        exception = ve.exception
        self.assertIn('Notification email must be a valid email address.', exception.message)
