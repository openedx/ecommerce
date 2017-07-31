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

    def _create_coupon_product_with_note_attribute(self, note):
        """Helper method that creates a coupon product with note attribute set."""
        coupon_product = factories.ProductFactory(
            title=self.COUPON_PRODUCT_TITLE,
            product_class=self.coupon_product_class
        )
        voucher = factories.VoucherFactory()
        coupon_vouchers = CouponVouchers.objects.create(coupon=coupon_product)
        coupon_vouchers.vouchers.add(voucher)
        coupon_product.attr.coupon_vouchers = coupon_vouchers
        coupon_product.attr.note = note
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
        coupon = self._create_coupon_product_with_note_attribute(note)
        self.assertEqual(coupon.attr.note, note)

    @ddt.data(1, {'some': 'dict'}, ['array'])
    def test_incorrect_note_value_raises_exception(self, note):
        """Verify creating product with invalid note type raises ValidationError."""
        with self.assertRaises(ValidationError):
            self._create_coupon_product_with_note_attribute(note)
