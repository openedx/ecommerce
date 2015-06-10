import ddt
from django.test import TestCase
from django_dynamic_fixture import G

from ecommerce.courses.models import Course
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

        # Associate the parent and child products with the course. The method should be able to filter out the parent.
        parent = seats.values()[0].parent
        parent.course = course
        parent.save()

        for seat in seats.itervalues():
            seat.course = course
            seat.save()

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
