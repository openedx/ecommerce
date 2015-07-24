import datetime
import json

import ddt
from django.conf import settings
from django.test import TestCase, override_settings
from django_dynamic_fixture import G
import httpretty
import mock
from requests import Timeout
from testfixtures import LogCapture

from ecommerce.courses.models import Course
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin

EDX_API_KEY = 'edx'
JSON = 'application/json'
LOGGER_NAME = 'ecommerce.courses.publishers'


@ddt.ddt
@override_settings(COMMERCE_API_URL='http://example.com/commerce/api/v1/', EDX_API_KEY=EDX_API_KEY)
class LMSPublisherTests(CourseCatalogTestMixin, TestCase):
    def setUp(self):
        super(LMSPublisherTests, self).setUp()
        self.course = G(Course)
        self.course.create_or_update_seat('honor', False, 0)
        self.course.create_or_update_seat('verified', True, 50)
        self.publisher = LMSPublisher()

    def _mock_commerce_api(self, status, body=None):
        self.assertTrue(httpretty.is_enabled, 'httpretty must be enabled to mock Commerce API calls.')

        body = body or {}
        url = '{}/courses/{}/'.format(settings.COMMERCE_API_URL.rstrip('/'), self.course.id)
        httpretty.register_uri(httpretty.PUT, url, status=status, body=json.dumps(body),
                               content_type=JSON)

    @ddt.data('', None)
    def test_commerce_api_url_not_set(self, setting_value):
        """ If the Commerce API is not setup, the method should log an INFO message and return """
        with override_settings(COMMERCE_API_URL=setting_value):
            with LogCapture(LOGGER_NAME) as l:
                self.publisher.publish(self.course)
                l.check((LOGGER_NAME, 'ERROR', 'COMMERCE_API_URL is not set. Commerce data will not be published!'))

    def test_api_exception(self):
        """ If an exception is raised when communicating with the Commerce API, an ERROR message should be logged. """
        with mock.patch('requests.put', side_effect=Timeout):
            with LogCapture(LOGGER_NAME) as l:
                self.publisher.publish(self.course)
                l.check(
                    (LOGGER_NAME, 'ERROR', 'Failed to publish commerce data for [{}] to LMS.'.format(self.course.id)))

    @httpretty.activate
    @ddt.data(401, 403, 404, 500)
    def test_api_bad_status(self, status):
        """ If the Commerce API returns a non-successful status, an ERROR message should be logged. """
        body = {u'error': u'Testing!'}
        self._mock_commerce_api(status, body)

        with LogCapture(LOGGER_NAME) as l:
            self.publisher.publish(self.course)
            l.check((LOGGER_NAME, 'ERROR',
                     u'Failed to publish commerce data for [{}] to LMS. Status was [{}]. Body was [{}].'.format(
                         self.course.id, status, json.dumps(body))))

    @httpretty.activate
    @ddt.data(200, 201)
    def test_api_success(self, status):
        """ If the Commerce API returns a successful status, an INFO message should be logged. """
        self._mock_commerce_api(status)

        with LogCapture(LOGGER_NAME) as l:
            self.publisher.publish(self.course)
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
            'modes': [self.publisher.serialize_seat_for_commerce_api(seat) for seat in self.course.seat_products]
        }
        self.assertDictEqual(actual, expected)

    def test_serialize_seat_for_commerce_api(self):
        """ The method should convert a seat to a JSON-serializable dict consumable by the Commerce API. """
        # Grab the verified seat
        seat = sorted(self.course.seat_products, key=lambda p: p.attr.certificate_type)[1]
        stock_record = seat.stockrecords.first()

        actual = self.publisher.serialize_seat_for_commerce_api(seat)
        expected = {
            'name': 'verified',
            'currency': 'USD',
            'price': int(stock_record.price_excl_tax),
            'sku': stock_record.partner_sku,
            'expires': None
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
        seat = self.course.create_or_update_seat('professional', is_verified, 500, expires=datetime.datetime.utcnow())
        stock_record = seat.stockrecords.first()
        actual = self.publisher.serialize_seat_for_commerce_api(seat)
        expected = {
            'name': expected_mode,
            'currency': 'USD',
            'price': int(stock_record.price_excl_tax),
            'sku': stock_record.partner_sku,
            'expires': None
        }
        self.assertDictEqual(actual, expected)
