from django.utils.timezone import now, timedelta

from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.testcases import TestCase


class ModelsTests(CourseCatalogTestMixin, TestCase):
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
