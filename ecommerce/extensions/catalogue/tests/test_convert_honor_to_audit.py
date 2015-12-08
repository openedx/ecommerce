import mock
from django.core.management import call_command
from oscar.core.loading import get_model

from ecommerce.courses.publishers import LMSPublisher
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.testcases import TestCase

ACCESS_TOKEN = 'secret'

Product = get_model('catalogue', 'Product')


class ConvertHonorToAuditTests(CourseCatalogTestMixin, TestCase):
    def setUp(self):
        super(ConvertHonorToAuditTests, self).setUp()
        self.course = CourseFactory()
        self.honor_seat = self.course.create_or_update_seat('honor', False, 0, self.partner)

    def test_honor_course(self):
        """ The command should delete the honor seat, and create a new audit seat. """
        # Mock the LMS call
        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            mock_publish.return_value = True
            call_command('convert_honor_to_audit', self.course.id, access_token=ACCESS_TOKEN, commit=True)

        # Verify honor seat deleted
        self.assertFalse(Product.objects.filter(id=self.honor_seat.id).exists())

        # Verify audit seat created
        audit_seats = [seat for seat in self.course.seat_products if getattr(seat.attr, 'certificate_type', '') == '']
        self.assertEqual(len(audit_seats), 1)

        # Verify data published to LMS
        self.assertTrue(mock_publish.called)

    def test_honor_course_without_commit(self):
        """ The command should raise an error and change no data if the commit flag is not set. """
        try:
            call_command('convert_honor_to_audit', self.course.id, access_token=ACCESS_TOKEN, commit=False)
            self.fail('An exception should be raised if the commit flag is not set.')
        except Exception:  # pylint: disable=broad-except
            pass

        # Verify honor seat still exists
        self.assertTrue(Product.objects.filter(id=self.honor_seat.id).exists())

        # Verify audit seat not in database
        audit_seats = [seat for seat in self.course.seat_products if getattr(seat.attr, 'certificate_type', '') == '']
        self.assertEqual(len(audit_seats), 0)
