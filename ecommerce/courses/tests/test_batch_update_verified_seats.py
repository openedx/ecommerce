"""Tests for the batch_update_verified_seats command"""
from decimal import Decimal
from unittest.mock import patch

import ddt
from django.core.management import call_command

from ecommerce.courses.models import Course
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.models import Product
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.testcases import TransactionTestCase


@ddt.ddt
class BatchUpdateVerifiedSeatsTests(DiscoveryTestMixin, TransactionTestCase):
    """
    Tests for the batch_update_verified_seats command.
    """
    def setUp(self):
        super().setUp()
        self.command = 'batch_update_verified_seats'

    def _create_courses_and_seats(self, count=1):
        """
        Create the specified number of courses with audit and verified seats. Verified seats
        will be saved with titles containing '(and ID verification)'.
        """
        for _ in range(count):
            course = CourseFactory(partner=self.partner)
            course.create_or_update_seat('audit', False, 0)
            verified_seat = course.create_or_update_seat('verified', True, Decimal(10.0))
            verified_seat.title = (
                f'Seat in {course.name} with verified certificate (and ID verification)'
            )
            verified_seat.save()

    def _get_seats_with_idv_title(self):
        """
        Get all seats containing "ID verification" in the title.
        """
        return Product.objects.filter(title__icontains='ID verification')

    def test_title_update(self):
        """
        Test that the command updates seat titles correctly.
        """
        self._create_courses_and_seats()

        verified_seat = self._get_seats_with_idv_title().first()
        self.assertEqual(
            verified_seat.title,
            f'Seat in {verified_seat.course.name} with verified certificate (and ID verification)'
        )

        call_command(self.command)

        updated_seat = Product.objects.get(id=verified_seat.id)
        self.assertEqual(
            updated_seat.title,
            f'Seat in {updated_seat.course.name} with verified certificate'
        )

    @ddt.data(1, 3, 5)
    def test_different_batch_sizes(self, course_count):
        """
        Test that the command can handle different batch sizes.
        """
        self._create_courses_and_seats(course_count)
        verified_seats = self._get_seats_with_idv_title()
        self.assertEqual(len(verified_seats), course_count)

        call_command(self.command, batch_size=3, sleep_time=1)
        updated_seats = self._get_seats_with_idv_title()
        self.assertEqual(len(updated_seats), 0)

    def test_create_or_update_seat_error(self):
        """
        Tests that errors are logged when failing to update seats.
        """
        self._create_courses_and_seats()

        with patch.object(Course, 'create_or_update_seat', side_effect=Exception('test')):
            with self.assertLogs(level='ERROR'):
                call_command(self.command)
