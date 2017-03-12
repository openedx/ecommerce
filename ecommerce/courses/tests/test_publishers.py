import datetime
import json

import ddt
import httpretty
import mock
from django.test import override_settings
from oscar.core.loading import get_model
from requests import Timeout
from testfixtures import LogCapture

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME, ENROLLMENT_CODE_SWITCH
from ecommerce.core.tests import toggle_switch
from ecommerce.core.url_utils import get_lms_commerce_api_url, get_lms_url
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.tests.testcases import TestCase

EDX_API_KEY = 'edx'
JSON = 'application/json'
LOGGER_NAME = 'ecommerce.courses.publishers'

StockRecord = get_model('partner', 'StockRecord')


@ddt.ddt
@override_settings(EDX_API_KEY=EDX_API_KEY)
class LMSPublisherTests(CourseCatalogTestMixin, TestCase):
    def setUp(self):
        super(LMSPublisherTests, self).setUp()
        self.course = CourseFactory(verification_deadline=datetime.datetime.now() + datetime.timedelta(days=7))
        self.course.create_or_update_seat('honor', False, 0, self.partner)
        self.course.create_or_update_seat('verified', True, 50, self.partner)
        self.publisher = LMSPublisher()
        self.error_message = u'Failed to publish commerce data for {course_id} to LMS.'.format(
            course_id=self.course.id
        )

    def _mock_commerce_api(self, status, body=None):
        self.assertTrue(httpretty.is_enabled(), 'httpretty must be enabled to mock Commerce API calls.')

        body = body or {}
        url = '{}/courses/{}/'.format(get_lms_commerce_api_url().rstrip('/'), self.course.id)
        httpretty.register_uri(httpretty.PUT, url, status=status, body=json.dumps(body),
                               content_type=JSON)

    def mock_creditcourse_endpoint(self, course_id, status, body=None):
        self.assertTrue(httpretty.is_enabled(), 'httpretty must be enabled to mock Credit API calls.')

        url = get_lms_url('/api/credit/v1/courses/{}/'.format(course_id))
        httpretty.register_uri(
            httpretty.PUT,
            url,
            status=status,
            body=json.dumps(body),
            content_type=JSON
        )

    @mock.patch('ecommerce.courses.publishers.get_lms_commerce_api_url', mock.Mock(return_value=None))
    def test_commerce_api_url_not_set(self):
        """ If the commerce API url cannot be retrieved, the method should log an ERROR message and return """
        with LogCapture(LOGGER_NAME) as l:
            response = self.publisher.publish(self.course)
            l.check(
                (LOGGER_NAME, 'ERROR', 'Commerce API URL is not set. Commerce data will not be published!')
            )
            self.assertIsNotNone(response)
            self.assertEqual(response, self.error_message)

    def test_api_exception(self):
        """ If an exception is raised when communicating with the Commerce API, an ERROR message should be logged. """
        error = 'time out error'
        with mock.patch('requests.put', side_effect=Timeout(error)):
            with LogCapture(LOGGER_NAME) as l:
                response = self.publisher.publish(self.course)
                l.check(
                    (
                        LOGGER_NAME, 'ERROR',
                        u'Failed to publish commerce data for [{course_id}] to LMS.'.format(
                            course_id=self.course.id
                        )
                    )
                )
                self.assertIsNotNone(response)
                self.assertEqual(self.error_message, response)

    @httpretty.activate
    @ddt.unpack
    @ddt.data(
        (400, {'non_field_errors': ['deadline issue']}, 'deadline issue'),
        (404, 'page not found', 'page not found'),
        (401, {'detail': 'Authentication'}, 'Authentication'),
        (401, {}, ''),
    )
    def test_api_bad_status(self, status, error_msg, expected_msg):
        """ If the Commerce API returns a non-successful status, an ERROR message should be logged. """
        self._mock_commerce_api(status, error_msg)
        with LogCapture(LOGGER_NAME) as l:
            response = self.publisher.publish(self.course)
            l.check(
                (
                    LOGGER_NAME, 'ERROR',
                    u'Failed to publish commerce data for [{}] to LMS. Status was [{}]. Body was [{}].'.format(
                        self.course.id, status, json.dumps(error_msg))
                )
            )

            self.assert_response_message(response, expected_msg)

    @httpretty.activate
    @ddt.data(200, 201)
    def test_api_success(self, status):
        """ If the Commerce API returns a successful status, an INFO message should be logged. """
        self._mock_commerce_api(status)

        with LogCapture(LOGGER_NAME) as l:
            response = self.publisher.publish(self.course)
            self.assertIsNone(response)

            l.check((LOGGER_NAME, 'INFO', 'Successfully published commerce data for [{}].'.format(self.course.id)))

        last_request = httpretty.last_request()

        # Verify the headers passed to the API were correct.
        expected = {
            'Content-Type': JSON,
            'X-Edx-Api-Key': EDX_API_KEY
        }
        self.assertDictContainsSubset(expected, last_request.headers)

        # Verify the data passed to the API was correct.
        actual = json.loads(last_request.body)
        expected = {
            'id': self.course.id,
            'name': self.course.name,
            'verification_deadline': self.course.verification_deadline.isoformat(),
            'modes': [self.publisher.serialize_seat_for_commerce_api(seat) for seat in self.course.seat_products]
        }
        self.assertDictEqual(actual, expected)

    def test_serialize_seat_for_commerce_api(self):
        """ The method should convert a seat to a JSON-serializable dict consumable by the Commerce API. """
        # Grab the verified seat
        seat = sorted(self.course.seat_products, key=lambda p: getattr(p.attr, 'certificate_type', ''))[1]
        stock_record = seat.stockrecords.first()

        actual = self.publisher.serialize_seat_for_commerce_api(seat)
        expected = {
            'name': 'verified',
            'currency': 'USD',
            'price': int(stock_record.price_excl_tax),
            'sku': stock_record.partner_sku,
            'bulk_sku': None,
            'expires': None,
        }
        self.assertDictEqual(actual, expected)

        # Try with an expiration datetime
        expires = datetime.datetime.utcnow()
        seat.expires = expires
        expected['expires'] = expires.isoformat()
        actual = self.publisher.serialize_seat_for_commerce_api(seat)
        self.assertDictEqual(actual, expected)

    @ddt.unpack
    @ddt.data(
        (True, 'professional'),
        (False, 'no-id-professional'),
    )
    def test_serialize_seat_for_commerce_api_with_professional(self, is_verified, expected_mode):
        """
        Verify that (a) professional seats NEVER have an expiration date and (b) the name/mode is properly set for
        no-id-professional seats.
        """
        seat = self.course.create_or_update_seat(
            'professional', is_verified, 500, self.partner, expires=datetime.datetime.utcnow()
        )
        stock_record = seat.stockrecords.first()
        actual = self.publisher.serialize_seat_for_commerce_api(seat)
        expected = {
            'name': expected_mode,
            'currency': 'USD',
            'price': int(stock_record.price_excl_tax),
            'sku': stock_record.partner_sku,
            'bulk_sku': None,
            'expires': None,
        }
        self.assertDictEqual(actual, expected)

    def test_serialize_seat_with_enrollment_code(self):
        toggle_switch(ENROLLMENT_CODE_SWITCH, True)
        seat = self.course.create_or_update_seat('verified', False, 10, self.partner, create_enrollment_code=True)
        stock_record = seat.stockrecords.first()
        ec_stock_record = StockRecord.objects.get(product__product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)

        actual = self.publisher.serialize_seat_for_commerce_api(seat)
        expected = {
            'name': 'verified',
            'currency': 'USD',
            'price': int(stock_record.price_excl_tax),
            'sku': stock_record.partner_sku,
            'bulk_sku': ec_stock_record.partner_sku,
            'expires': None,
        }
        self.assertDictEqual(actual, expected)

    def attempt_credit_publication(self, api_status):
        """
        Sets up a credit seat and attempts to publish it to LMS.

        Returns
            String - Publish error message.
        """
        # Setup the course and mock the API endpoints
        self.course.create_or_update_seat('credit', True, 100, self.partner, credit_provider='acme', credit_hours=1)
        self.mock_creditcourse_endpoint(self.course.id, api_status)
        self._mock_commerce_api(201)

        # Attempt to publish the course
        return self.publisher.publish(self.course, access_token='access_token')

    def assert_creditcourse_endpoint_called(self):
        """ Verify the Credit API's CreditCourse endpoint was called. """
        last_request = httpretty.httpretty.latest_requests[0]
        self.assertEqual(last_request.path, '/api/credit/v1/courses/{}/'.format(self.course.id))

    @httpretty.activate
    def test_credit_publication_success(self):
        """ Verify the endpoint returns successfully when credit publication succeeds. """
        error_message = self.attempt_credit_publication(201)
        self.assertIsNone(error_message)
        self.assert_creditcourse_endpoint_called()

    @httpretty.activate
    def test_credit_publication_api_failure(self):
        """ Verify the endpoint fails appropriately when Credit API calls return an error. """
        course_id = self.course.id
        with LogCapture(LOGGER_NAME) as l:
            status = 400
            actual = self.attempt_credit_publication(status)

            # Ensure the HTTP status and response are logged
            expected_log = 'Failed to publish CreditCourse for [{course_id}] to LMS. ' \
                           'Status was [{status}]. Body was \'null\'.'.format(course_id=course_id, status=status)
            l.check((LOGGER_NAME, 'ERROR', expected_log))

        expected = 'Failed to publish commerce data for {} to LMS.'.format(course_id)
        self.assertEqual(actual, expected)
        self.assert_creditcourse_endpoint_called()

    @httpretty.activate
    @mock.patch('requests.get', mock.Mock(side_effect=Exception))
    def test_credit_publication_uncaught_exception(self):
        """ Verify the endpoint fails appropriately when the Credit API fails unexpectedly. """
        actual = self.attempt_credit_publication(500)
        expected = 'Failed to publish commerce data for {} to LMS.'.format(self.course.id)
        self.assertEqual(actual, expected)

    def assert_response_message(self, api_response, expected_error_msg):
        self.assertIsNotNone(api_response)
        if expected_error_msg:
            self.assertEqual(api_response, " ".join([self.error_message, expected_error_msg]))
        else:
            self.assertEqual(api_response, self.error_message, expected_error_msg)
