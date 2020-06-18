

import datetime
import json

import ddt
import httpretty
import mock
from django.utils import timezone
from oscar.core.loading import get_model
from requests import Timeout
from testfixtures import LogCapture

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME
from ecommerce.core.url_utils import get_lms_url
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'
LOGGER_NAME = 'ecommerce.courses.publishers'

StockRecord = get_model('partner', 'StockRecord')


@ddt.ddt
class LMSPublisherTests(DiscoveryTestMixin, TestCase):
    def setUp(self):
        super(LMSPublisherTests, self).setUp()

        httpretty.enable()
        self.mock_access_token_response()

        self.course = CourseFactory(
            verification_deadline=timezone.now() + datetime.timedelta(days=7),
            partner=self.partner
        )
        self.course.create_or_update_seat('honor', False, 0)
        self.course.create_or_update_seat('verified', True, 50)
        self.publisher = LMSPublisher()
        self.error_message = 'Failed to publish commerce data for {course_id} to LMS.'.format(course_id=self.course.id)

    def tearDown(self):
        super(LMSPublisherTests, self).tearDown()
        httpretty.disable()
        httpretty.reset()

    def _mock_commerce_api(self, status=200, body=None):
        self.assertTrue(httpretty.is_enabled(), 'httpretty must be enabled to mock Commerce API calls.')

        body = body or {}
        url = self.site_configuration.build_lms_url('/api/commerce/v1/courses/{}/'.format(self.course.id))
        httpretty.register_uri(httpretty.PUT, url, status=status, body=json.dumps(body), content_type=JSON)

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

    def test_api_exception(self):
        """ If an exception is raised when communicating with the Commerce API, an ERROR message should be logged. """
        error = 'time out error'
        with mock.patch('requests.put', side_effect=Timeout(error)):
            with LogCapture(LOGGER_NAME) as logger:
                actual = self.publisher.publish(self.course)
                logger.check(
                    (
                        LOGGER_NAME, 'ERROR',
                        'Failed to publish commerce data for [{course_id}] to LMS.'.format(course_id=self.course.id)
                    )
                )
                self.assertEqual(actual, self.error_message)

    def test_api_error(self):
        """ If the Commerce API returns a non-successful status, an ERROR message should be logged. """
        status = 400
        expected_msg = 'deadline issue'
        api_body = {'non_field_errors': [expected_msg]}

        self._mock_commerce_api(status, api_body)
        with LogCapture(LOGGER_NAME) as logger:
            actual = self.publisher.publish(self.course)
            logger.check(
                (
                    LOGGER_NAME, 'ERROR',
                    'Failed to publish commerce data for [{}] to LMS. Status was [{}]. Body was [{}].'.format(
                        self.course.id, status, json.dumps(api_body))
                )
            )

            self.assertEqual(actual, self.error_message + ' ' + expected_msg)

    def test_api_success(self):
        """ If the Commerce API returns a successful status, an INFO message should be logged. """
        self._mock_commerce_api()

        with LogCapture(LOGGER_NAME) as logger:
            response = self.publisher.publish(self.course)
            self.assertIsNone(response)

            logger.check((LOGGER_NAME, 'INFO', 'Successfully published commerce data for [{}].'.format(self.course.id)))

        last_request = httpretty.last_request()

        # Verify the data passed to the API was correct.
        actual = json.loads(last_request.body.decode('utf-8'))
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
            'professional', is_verified, 500, expires=datetime.datetime.utcnow()
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
        seat = self.course.create_or_update_seat('verified', False, 10, create_enrollment_code=True)
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
        self.course.create_or_update_seat('credit', True, 100, credit_provider='acme', credit_hours=1)
        self.mock_creditcourse_endpoint(self.course.id, api_status)
        self._mock_commerce_api(201)

        # Attempt to publish the course
        return self.publisher.publish(self.course)

    def assert_creditcourse_endpoint_called(self):
        """ Verify the Credit API's CreditCourse endpoint was called. """
        paths = [request.path for request in httpretty.httpretty.latest_requests]
        self.assertIn('/api/credit/v1/courses/{}/'.format(self.course.id), paths)

    def test_credit_publication_success(self):
        """ Verify the endpoint returns successfully when credit publication succeeds. """
        error_message = self.attempt_credit_publication(201)
        self.assertIsNone(error_message)
        self.assert_creditcourse_endpoint_called()

    def test_credit_publication_api_failure(self):
        """ Verify the endpoint fails appropriately when Credit API calls return an error. """
        course_id = self.course.id
        with LogCapture(LOGGER_NAME) as logger:
            status = 400
            actual = self.attempt_credit_publication(status)

            # Ensure the HTTP status and response are logged
            expected_log = 'Failed to publish CreditCourse for [{course_id}] to LMS. ' \
                           'Status was [{status}]. Body was [null].'.format(course_id=course_id, status=status)
            logger.check((LOGGER_NAME, 'ERROR', expected_log))

        expected = 'Failed to publish commerce data for {} to LMS.'.format(course_id)
        self.assertEqual(actual, expected)
        self.assert_creditcourse_endpoint_called()

    @mock.patch('requests.get', mock.Mock(side_effect=Exception))
    def test_credit_publication_uncaught_exception(self):
        """ Verify the endpoint fails appropriately when the Credit API fails unexpectedly. """
        actual = self.attempt_credit_publication(500)
        expected = 'Failed to publish commerce data for {} to LMS.'.format(self.course.id)
        self.assertEqual(actual, expected)
