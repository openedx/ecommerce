import ddt
from django.test import TestCase
from django_dynamic_fixture import G
import mock
from testfixtures import LogCapture
from waffle import Switch

from ecommerce.courses.models import Course
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin


@ddt.ddt
class CourseTests(CourseCatalogTestMixin, TestCase):
    def test_unicode(self):
        """Verify the __unicode__ method returns the Course ID."""
        course_id = u'edx/Demo_Course/DemoX'
        course = Course.objects.create(id=course_id)
        self.assertEqual(unicode(course), course_id)

    def test_seat_products(self):
        """
        Verify the method returns a list containing purchasable course seats.

        These seats should be the child products.
        """
        # Create a new course and verify it has no existing products.
        course = G(Course)
        self.assertEqual(course.products.count(), 0)
        self.assertEqual(len(course.seat_products), 0)

        # Create the seat products
        seats = self.create_course_seats(course.id, ('honor', 'verified'))
        self.assertEqual(course.products.count(), 3)

        # The method should return only the child seats.
        # We do not necessarily care about the order, but must sort to check equality.
        expected = seats.values().sort()
        self.assertEqual(course.seat_products.sort(), expected)

    @ddt.data(
        ('verified', True),
        ('credit', True),
        ('professional', True),
        ('honor', False),
        ('no-id-professional', False),
        ('audit', False),
        ('unknown', False),
    )
    @ddt.unpack
    def test_is_mode_verified(self, mode, expected):
        """ Verify the method returns True only for verified modes. """
        self.assertEqual(Course.is_mode_verified(mode), expected)

    @ddt.data(
        ('Verified', 'verified'),
        ('credit', 'credit'),
        ('professional', 'professional'),
        ('honor', 'honor'),
        ('no-id-professional', 'professional'),
        ('audit', 'audit'),
        ('unknown', 'unknown'),
    )
    @ddt.unpack
    def test_certificate_type_for_mode(self, mode, expected):
        """ Verify the method returns the correct certificate type for a given mode. """
        self.assertEqual(Course.certificate_type_for_mode(mode), expected)

    def test_save_and_publish_to_lms(self):
        """
        Verify the save method calls the LMS publisher if the feature is enabled.
        """
        switch, __ = Switch.objects.get_or_create(name='publish_course_modes_to_lms', active=False)
        course = G(Course)

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            logger_name = 'ecommerce.courses.models'
            with LogCapture(logger_name) as l:
                course.save()
                l.check((logger_name, 'DEBUG',
                         'Course mode publishing is not enabled. Commerce changes will not be published!'))

            self.assertFalse(mock_publish.called)

            # Reset the mock and activate the feature.
            mock_publish.reset_mock()
            switch.active = True
            switch.save()

            # With the feature active, the mock method should be called.
            course.save()
            mock_publish.assert_called_with(course)

    def test_save_with_publish_failure(self):
        """ Verify that, if the publish operation fails, the model's changes are not saved to the database. """
        orignal_name = 'A Most Awesome Course'
        course = G(Course, name=orignal_name)
        Switch.objects.get_or_create(name='publish_course_modes_to_lms', active=True)

        # Mock an error in the publisher
        with mock.patch.object(LMSPublisher, 'publish', return_value=False):
            course.name = 'An Okay Course'

        # Reload the course from the database
        course = Course.objects.get(id=course.id)
        self.assertEqual(course.name, orignal_name)
