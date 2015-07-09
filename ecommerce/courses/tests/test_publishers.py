import datetime
from decimal import Decimal
import json

import ddt
from django.conf import settings
from django.test import TestCase, override_settings
from django_dynamic_fixture import G
import httpretty
import mock
from oscar.test import factories
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
        self.create_course_seats(self.course.id, ('honor', 'verified'))
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
        seat = factories.ProductFactory(product_class=self.seat_product_class, expires=None)
        certificate_type = 'honor'
        seat.attr.certificate_type = certificate_type
        seat.save()

        seat.stockrecords.all().delete()
        stock_record = factories.StockRecordFactory(product=seat, partner_sku='ABC123', price_currency='USD',
                                                    price_excl_tax=Decimal('10'))

        actual = self.publisher.serialize_seat_for_commerce_api(seat)
        expected = {
            'name': certificate_type,
            'currency': stock_record.price_currency,
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
