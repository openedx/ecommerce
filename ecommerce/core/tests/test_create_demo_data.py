

import sys
from datetime import datetime
from io import StringIO

import httpretty
import mock
import pytz
from django.core.management import call_command

from ecommerce.courses.models import Course
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.testcases import TestCase


class CreateDemoDataTests(DiscoveryTestMixin, TestCase):
    def assert_seats_created(self, course_id, course_title, price):
        course = Course.objects.get(id=course_id, name=course_title)
        seats = course.seat_products

        audit_seat = seats[1]
        self.assertFalse(hasattr(audit_seat.attr, 'certificate_type'))
        self.assertFalse(audit_seat.attr.id_verification_required)
        self.assertEqual(audit_seat.stockrecords.get(partner=self.partner).price_excl_tax, 0)

        verified_seat = seats[0]
        self.assertEqual(verified_seat.attr.certificate_type, 'verified')
        self.assertTrue(verified_seat.attr.id_verification_required)
        self.assertEqual(verified_seat.stockrecords.get(partner=self.partner).price_excl_tax, price)

    @httpretty.activate
    def test_handle(self):
        """ The command should create the demo course with audit and verified seats,
        and publish that data to the LMS.
        """
        self.mock_access_token_response()

        with mock.patch.object(Course, 'publish_to_lms', return_value=None) as mock_publish:
            call_command('create_demo_data', '--partner={}'.format(self.partner.short_code))
            mock_publish.assert_called_once_with()

        self.assert_seats_created('course-v1:edX+DemoX+Demo_Course', 'edX Demonstration Course', 149)

    @httpretty.activate
    def test_handle_with_existing_course(self):
        """ The command should create the demo course with audit and verified seats,
        and publish that data to the LMS.
        """
        self.mock_access_token_response()

        course = CourseFactory(
            id='course-v1:edX+DemoX+Demo_Course',
            name='edX Demonstration Course',
            verification_deadline=datetime(year=2022, month=4, day=24, tzinfo=pytz.utc),
            partner=self.partner
        )

        seat_attrs = {'certificate_type': '', 'expires': None, 'price': 0.00, 'id_verification_required': False}
        course.create_or_update_seat(**seat_attrs)

        with mock.patch.object(Course, 'publish_to_lms', return_value=None) as mock_publish:
            call_command('create_demo_data', '--partner={}'.format(self.partner.short_code))
            mock_publish.assert_called_once_with()

        self.assert_seats_created('course-v1:edX+DemoX+Demo_Course', 'edX Demonstration Course', 149)

    @httpretty.activate
    def test_handle_with_overrides(self):
        """ Users should be able to specify the course ID, course title, and price of the verified seat. """
        course_id = 'a/b/c'
        course_title = 'ABCs'
        price = 1e6
        self.mock_access_token_response()

        with mock.patch.object(Course, 'publish_to_lms', return_value=None) as mock_publish:
            call_command('create_demo_data', '--partner={}'.format(self.partner.short_code), course_id=course_id,
                         course_title=course_title, price=price)
            mock_publish.assert_called_once_with()

        self.assert_seats_created(course_id, course_title, price)

    @httpretty.activate
    def test_handle_with_error_in_publish_to_lms(self):
        """
        The command should log error message if there was an error in publish to LMS.
        """
        err_out = StringIO()
        sys.stderr = err_out
        with mock.patch.object(Course, 'publish_to_lms', return_value="Failed to publish"):
            call_command('create_demo_data', '--partner={}'.format(self.partner.short_code))
            output = err_out.getvalue().strip()
            self.assertIn("An error occurred while attempting to publish", output)
