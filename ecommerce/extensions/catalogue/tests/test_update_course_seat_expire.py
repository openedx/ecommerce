# encoding: utf-8


import datetime
import json
import logging

import ddt
import httpretty
import mock
from django.core.management import CommandError, call_command
from pytz import UTC
from slumber.exceptions import HttpClientError
from testfixtures import LogCapture

from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.models import Product
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.testcases import TestCase

logger = logging.getLogger(__name__)
LOGGER_NAME = 'ecommerce.extensions.catalogue.management.commands.update_course_seat_expire'
JSON = 'application/json'


@ddt.ddt
class UpdateSeatExpireDateTests(DiscoveryTestMixin, TestCase):
    """Tests the update course seat expire command ."""

    def setUp(self):
        """ Setup course and seats required to run tests """
        super(UpdateSeatExpireDateTests, self).setUp()
        now = datetime.datetime.now(tz=UTC)
        self.expire_date = now - datetime.timedelta(days=7)
        self.verified_expire_date = now - datetime.timedelta(days=8)
        self.seats_to_update = ['honor', 'audit', 'no-id-professional', 'professional']
        self.course = CourseFactory(partner=self.partner)
        self.course_info = {
            'pagination': {},
            'results': [
                {
                    'enrollment_end': str(self.expire_date),
                    'course_id': self.course.id
                },
            ],
        }

        self.honor_seat = self.course.create_or_update_seat('honor', False, 0)
        self.verified_seat = self.course.create_or_update_seat(
            'verified', False, 500, expires=self.verified_expire_date
        )
        self.professional_seat = self.course.create_or_update_seat('professional', False, 0)

    def mock_courses_api(self, status, body=None):
        """ Mock Courses API with specific status and body. """
        self.assertTrue(httpretty.is_enabled(), 'httpretty must be enabled to mock Course API calls.')

        body = body or {}
        url = get_lms_url('/api/courses/v1/courses/?page_size=1')
        httpretty.register_uri(
            httpretty.GET,
            url,
            status=status,
            body=json.dumps(body),
            content_type=JSON
        )

    @httpretty.activate
    def test_update_course_with_commit(self):
        """ Verify all course seats are updated successfully, when commit option is provided. """
        seats_expected_to_update = self.course.seat_products.filter(
            attributes__name='certificate_type',
            attribute_values__value_text__in=self.seats_to_update
        )
        self.mock_courses_api(status=200, body=self.course_info)

        expected = [
            (
                LOGGER_NAME,
                'INFO',
                '[1] courses found for update.'
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Updated expiration date for [{}] seats: [{}]'.format(
                    self.course.id,
                    ', '.join([str(seat.id) for seat in seats_expected_to_update])
                )
            ),
        ]

        with LogCapture(LOGGER_NAME) as lc:
            call_command('update_course_seat_expire', commit=True)
            lc.check(*expected)

        # Verify course seats have been updated
        for seat in seats_expected_to_update:
            fetched_seat = Product.objects.get(id=seat.id)
            self.assertIsNotNone(fetched_seat.expires)
            self.assertEqual(fetched_seat.expires, self.expire_date)

        # Verify that 'verified' seat has not been updated.
        verified_seat = Product.objects.get(id=self.verified_seat.id)
        self.assertEqual(verified_seat.expires, self.verified_expire_date)

    @httpretty.activate
    def test_update_course_without_commit(self):
        """ Verify all course seats are not updated with commit option is not provided. """
        seats_expected_to_update = self.course.seat_products.filter(
            attributes__name='certificate_type',
            attribute_values__value_text__in=self.seats_to_update
        )
        self.mock_courses_api(status=200, body=self.course_info)

        expected = [
            (
                LOGGER_NAME,
                'INFO',
                '[1] courses found for update.'
            ),
        ]

        with LogCapture(LOGGER_NAME) as lc:
            call_command('update_course_seat_expire', commit=False)
            lc.check(*expected)

        # Verify course seats have not been updated
        for seat in seats_expected_to_update:
            fetched_seat = Product.objects.get(id=seat.id)
            self.assertIsNone(fetched_seat.expires)

        # Verify that 'verified' seat has not been updated.
        verified_seat = Product.objects.get(id=self.verified_seat.id)
        self.assertEqual(verified_seat.expires, self.verified_expire_date)

    @httpretty.activate
    def test_update_course_with_no_data(self):
        """ Verify all course seats are updated successfully, when commit option is provided"""
        self.course_info['results'] = []
        self.mock_courses_api(status=200, body=self.course_info)

        expected = [
            (
                LOGGER_NAME,
                'ERROR',
                'No course enrollment information found.'
            )
        ]

        with LogCapture(LOGGER_NAME) as lc:
            with self.assertRaises(CommandError):
                call_command('update_course_seat_expire')
                lc.check(*expected)

    @httpretty.activate
    def test_update_course_with_missing_enrolment(self):
        """
        Verify that management command logs `enrollment missing` log for all courses
        which are missing `enrollment_end` date.
        """
        self.course_info['results'][0]['enrollment_end'] = None
        self.mock_courses_api(status=200, body=self.course_info)

        expected = [
            (
                LOGGER_NAME,
                'INFO',
                '[1] courses found for update.'
            ),
            (
                LOGGER_NAME,
                'ERROR',
                'Enrollment missing for course [{}]'.format(self.course.id)
            )
        ]

        with LogCapture(LOGGER_NAME) as lc:
            call_command('update_course_seat_expire')
            lc.check(*expected)

    @httpretty.activate
    @mock.patch(
        'ecommerce.extensions.catalogue.management.commands.update_course_seat_expire.Command.max_tries',
        new_callable=mock.PropertyMock,
        return_value=1
    )
    @mock.patch(
        'ecommerce.extensions.catalogue.management.commands.update_course_seat_expire.Command.pause_time',
        new_callable=mock.PropertyMock,
        return_value=1
    )
    def test_update_course_with_exception(self, mock_max_tries, mock_pause_time):
        """
        Verify that management command logs throttling errors when rate-limit to API
        exceeds.
        """
        self.mock_courses_api(status=429, body=self.course_info)
        expected = [
            (
                LOGGER_NAME,
                'WARNING',
                'API calls are being rate-limited. Waiting for [1] seconds before retrying...'
            ),
            (
                LOGGER_NAME,
                'INFO',
                'Retrying [1]'
            ),
        ]
        with self.assertRaises(HttpClientError):
            with LogCapture(LOGGER_NAME) as lc:
                call_command('update_course_seat_expire')
                lc.check(*expected)

        self.assertEqual(mock_max_tries.call_count, 2)
        self.assertEqual(mock_pause_time.call_count, 2)
