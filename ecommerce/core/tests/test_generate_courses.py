import json
import ddt
import httpretty
import mock
from django.core.management import CommandError, call_command
from django.test import override_settings

from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class GenerateCoursesTests(DiscoveryTestMixin, TestCase):

    default_verified_price = 100
    default_professional_price = 1000

    def test_invalid_env(self):
        """
        Test that running the command in a non-development environment will raise the appropriate command error
        """
        msg = "Command should only be run in development environments"
        with self.assertRaisesRegexp(CommandError, msg):
            arg = 'arg'
            call_command("generate_courses", arg)

    @override_settings(DEBUG=True)
    def test_invalid_json(self):
        """
        Test that providing an invalid JSON object will raise the appropriate command error
        """
        msg = "Invalid JSON object"
        with self.assertRaisesRegexp(CommandError, msg):
            arg = 'invalid_json'
            call_command("generate_courses", arg)

    @override_settings(DEBUG=True)
    def test_missing_courses_field(self):
        """
        Test that missing the courses key will raise the appropriate command error
        """
        msg = "JSON object is missing courses field"
        with self.assertRaisesRegexp(CommandError, msg):
            arg = ('{}')
            call_command("generate_courses", arg)

    @override_settings(DEBUG=True)
    @mock.patch('ecommerce.core.management.commands.generate_courses.logger')
    @ddt.data("organization", "number", "run", "fields", "seats")
    def test_missing_course_setting(self, setting, mock_logger):
        """
        Test that missing settings in course JSON will result in the appropriate log messages
        """
        msg = "Course json is missing the following fields: " + str([setting])
        settings = {"courses": [{
            "store": "split",
            "organization": "test-course-generator",
            "number": "1",
            "run": "1",
            "fields": {"display_name": "test-course"},
            "seats": []
        }]}
        del settings["courses"][0][setting]
        arg = json.dumps(settings)
        call_command("generate_courses", arg)
        mock_logger.warning.assert_any_call(msg)

    @override_settings(DEBUG=True)
    @mock.patch('ecommerce.core.management.commands.generate_courses.logger')
    def test_missing_course_name(self, mock_logger):
        """
        Test that missing course name in fields json will result in the appropriate log messages
        """
        msg = "Fields json is missing display_name"
        settings = {"courses": [{
            "store": "split",
            "organization": "test-course-generator",
            "number": "1",
            "run": "1",
            "fields": {},
            "seats": []
        }]}
        arg = json.dumps(settings)
        call_command("generate_courses", arg)
        mock_logger.warning.assert_any_call(msg)

    @override_settings(DEBUG=True)
    @mock.patch('ecommerce.core.management.commands.generate_courses.logger')
    def test_invalid_seat_type(self, mock_logger):
        """
        Test that an invalid seat type in seat JSON will result in the appropriate log messages
        """
        valid_seat_types = ["audit", "verified", "honor", "professional"]
        msg = "Seat type must be one of %s" % (valid_seat_types)
        settings = {"courses": [{
            "store": "split",
            "organization": "test-course-generator",
            "number": "1",
            "run": "1",
            "fields": {"display_name": "test-course"},
            "seats": [{"seat_type": "invalid_seat_type"}]
        }]}
        arg = json.dumps(settings)
        call_command("generate_courses", arg)
        mock_logger.warning.assert_any_call(msg)

    @override_settings(DEBUG=True)
    @httpretty.activate
    @ddt.data("audit", "honor", "verified", "professional")
    def test_create_seat(self, seat_type):
        """
        The command should create the demo course with a seat,
        and publish that data to the LMS.
        """
        if seat_type == "verified":
            price = self.default_verified_price
        elif seat_type == "professional":
            price = self.default_professional_price
        else:
            price = 0

        self.mock_access_token_response()
        settings = {"courses": [{
            "store": "split",
            "organization": "test-course-generator",
            "number": "1",
            "run": "1",
            "fields": {"display_name": "test-course"},
            "seats": [{"seat_type": seat_type}]
        }]}
        arg = json.dumps(settings)
        with mock.patch.object(Course, 'publish_to_lms', return_value=None) as mock_publish:
            call_command('generate_courses', arg)
            mock_publish.assert_called_once_with()

        course = Course.objects.get(id='course-v1:test-course-generator+1+1')
        seats = course.seat_products
        seat = seats[0]
        self.assertEqual(seat.stockrecords.get(partner=self.partner).price_excl_tax, price)
