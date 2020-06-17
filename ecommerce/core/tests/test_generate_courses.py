

import json

import ddt
import httpretty
import mock
from django.core.management import CommandError, call_command

from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class GenerateCoursesTests(DiscoveryTestMixin, TestCase):

    def test_invalid_json(self):
        """
        Test that providing an invalid JSON object will raise the appropriate command error
        """
        with self.assertRaisesRegex(CommandError, "Invalid JSON object"):
            arg = 'invalid_json'
            call_command("generate_courses", arg)

    def test_missing_course_list(self):
        """
        Test that missing the courses key will raise the appropriate command error
        """
        with self.assertRaisesRegex(CommandError, "JSON object is missing courses list"):
            arg = ('{}')
            call_command("generate_courses", arg)

    @mock.patch('ecommerce.core.management.commands.generate_courses.logger')
    @ddt.data("organization", "number", "run", "partner", "fields", "enrollment")
    def test_missing_course_setting(self, setting, mock_logger):
        """
        Test that missing settings in course JSON will result in the appropriate log messages
        """
        settings = {"courses": [{
            "organization": "test-course-generator",
            "number": "1",
            "run": "1",
            "partner": str(self.partner.short_code),
            "fields": {"display_name": "test-course"},
            "enrollment": {}
        }]}
        del settings["courses"][0][setting]
        arg = json.dumps(settings)
        call_command("generate_courses", arg)
        mock_logger.warning.assert_any_call("Course json is missing %s", setting)

    @mock.patch('ecommerce.core.management.commands.generate_courses.logger')
    def test_invalid_partner(self, mock_logger):
        """
        Test that supplying an invalid partner in course JSON will result in the appropriate log messages
        """
        invalid_partner = "invalid_partner"
        settings = {"courses": [{
            "organization": "test-course-generator",
            "number": "1",
            "run": "1",
            "partner": invalid_partner,
            "fields": {"display_name": "test-course"},
            "enrollment": {
                "audit": False,
                "honor": False,
                "verified": False,
                "professional_education": False,
                "no_id_verification": False,
                "credit": False,
                "credit_provider": None
            }
        }]}
        arg = json.dumps(settings)
        call_command("generate_courses", arg)
        mock_logger.warning.assert_any_call(
            "%s partner does not exist. Can't create course, proceeding to next course.",
            invalid_partner
        )

    @mock.patch('ecommerce.core.management.commands.generate_courses.logger')
    def test_missing_course_name(self, mock_logger):
        """
        Test that missing course name in fields json will result in the appropriate log messages
        """
        settings = {"courses": [{
            "organization": "test-course-generator",
            "number": "1",
            "run": "1",
            "partner": str(self.partner.short_code),
            "fields": {},
            "enrollment": {}
        }]}
        arg = json.dumps(settings)
        call_command("generate_courses", arg)
        mock_logger.warning.assert_any_call("Fields json is missing %s", "display_name")

    @mock.patch('ecommerce.core.management.commands.generate_courses.logger')
    def test_invalid_enrollment_setting(self, mock_logger):
        """
        Test that an invalid setting in enrollment JSON will result in the appropriate log messages
        """
        settings = {"courses": [{
            "organization": "test-course-generator",
            "number": "1",
            "run": "1",
            "partner": str(self.partner.short_code),
            "fields": {"display_name": "test-course"},
            "enrollment": {
                "invalid_setting": "invalid_value",
                "audit": False,
                "honor": False,
                "verified": False,
                "professional_education": False,
                "no_id_verification": False,
                "credit": False,
                "credit_provider": None
            }
        }]}
        arg = json.dumps(settings)
        call_command("generate_courses", arg)
        mock_logger.info.assert_any_call("%s is not a recognized enrollment setting", "invalid_setting")

    @mock.patch('ecommerce.core.management.commands.generate_courses.logger')
    @ddt.data("audit", "honor", "verified", "professional_education", "no_id_verification")
    def test_missing_enrollment_setting(self, enrollment_setting, mock_logger):
        """
        Test that missing setting in enrollment JSON will result in the appropriate log messages
        """
        settings = {"courses": [{
            "organization": "test-course-generator",
            "number": "1",
            "run": "1",
            "partner": str(self.partner.short_code),
            "fields": {"display_name": "test-course"},
            "enrollment": {
                "audit": False,
                "honor": False,
                "verified": False,
                "professional_education": False,
                "no_id_verification": False,
                "credit": False,
                "credit_provider": None
            }
        }]}
        del settings["courses"][0]["enrollment"][enrollment_setting]
        arg = json.dumps(settings)
        call_command("generate_courses", arg)
        mock_logger.warning.assert_any_call("Enrollment json is missing %s", enrollment_setting)

    @httpretty.activate
    @mock.patch('ecommerce.core.management.commands.generate_courses.logger')
    @ddt.data("audit", "honor", "verified", "professional_education", "credit")
    def test_create_seat(self, seat_type, mock_logger):
        """
        The command should create the demo course with a seat,
        and publish that data to the LMS.
        """
        if seat_type == "verified":
            price = 100
        elif seat_type == "professional_education":
            price = 1000
        elif seat_type == "credit":
            price = 2000
        else:
            price = 0

        self.mock_access_token_response()
        settings = {"courses": [{
            "organization": "test-course-generator",
            "number": "1",
            "run": "1",
            "fields": {"display_name": "test-course"},
            "partner": str(self.partner.short_code),
            "enrollment": {
                "audit": False,
                "honor": False,
                "verified": False,
                "professional_education": False,
                "no_id_verification": False,
                "credit": False,
                "credit_provider": None,
            }
        }]}
        settings["courses"][0]["enrollment"][seat_type] = True
        arg = json.dumps(settings)
        with mock.patch.object(Course, 'publish_to_lms', return_value=None) as mock_publish:
            call_command('generate_courses', arg)
            mock_publish.assert_called_once_with()

        course = Course.objects.get(id='course-v1:test-course-generator+1+1')
        seats = course.seat_products
        seat = seats[0]
        self.assertEqual(seat.stockrecords.get(partner=self.partner).price_excl_tax, price)
        mock_logger.info.assert_any_call("%s has been set to %s", seat_type, True)
