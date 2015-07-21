# coding=utf-8
from __future__ import unicode_literals
import datetime
import json
import logging
from urlparse import urljoin
from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
import httpretty
from oscar.core.loading import get_model
import pytz

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.management.commands.migrate_course import MigratedCourse
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.catalogue.utils import generate_sku

JSON = 'application/json'
ACCESS_TOKEN = 'edx'
EXPIRES = datetime.datetime(year=1985, month=10, day=26, hour=1, minute=20, tzinfo=pytz.utc)
EXPIRES_STRING = EXPIRES.strftime(ISO_8601_FORMAT)

logger = logging.getLogger(__name__)

Category = get_model('catalogue', 'Category')
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')


class CourseMigrationTestMixin(CourseCatalogTestMixin):
    course_id = 'aaa/bbb/ccc'

    prices = {
        'honor': 0,
        'verified': 10,
        'no-id-professional': 100,
        'professional': 1000
    }

    def _mock_lms_api(self):
        self.assertTrue(httpretty.is_enabled, 'httpretty must be enabled to mock LMS API calls.')

        # Mock Course Structure API
        url = urljoin(settings.LMS_URL_ROOT, 'api/course_structure/v0/courses/{}/'.format(self.course_id))
        httpretty.register_uri(httpretty.GET, url, body='{"name": "A Tést Côurse"}', content_type=JSON)

        # Mock Enrollment API
        url = urljoin(settings.LMS_URL_ROOT, 'api/enrollment/v1/course/{}'.format(self.course_id))
        body = {
            'course_id': self.course_id,
            'course_modes': [{'slug': seat_type, 'min_price': price, 'expiration_datetime': EXPIRES_STRING} for
                             seat_type, price in self.prices.iteritems()]
        }
        httpretty.register_uri(httpretty.GET, url, body=json.dumps(body), content_type=JSON)

    def assert_stock_record_valid(self, stock_record, seat, price):
        """ Verify the given StockRecord is configured correctly. """
        self.assertEqual(stock_record.partner, self.partner)
        self.assertEqual(stock_record.price_excl_tax, price)
        self.assertEqual(stock_record.price_currency, 'USD')
        self.assertEqual(stock_record.partner_sku, generate_sku(seat))

    def assert_seat_valid(self, seat, certificate_type):
        """ Verify the given seat is configured correctly. """
        certificate_type = Course.certificate_type_for_mode(certificate_type)

        expected_title = 'Seat in A Tést Côurse with {} certificate'.format(certificate_type)
        if seat.attr.id_verification_required:
            expected_title += u' (and ID verification)'

        self.assertEqual(seat.title, expected_title)
        self.assertEqual(seat.attr.certificate_type, certificate_type)
        self.assertEqual(seat.expires, EXPIRES)
        self.assertEqual(seat.attr.certificate_type, certificate_type)
        self.assertEqual(seat.attr.course_key, self.course_id)
        # self.assertEqual(seat.attr.id_verification_required, Course.is_mode_verified(certificate_type))

    def assert_course_migrated(self):
        """ Verify the course was migrated and saved to the database. """
        course = Course.objects.get(id=self.course_id)
        seats = course.seat_products
        self.assertEqual(len(seats), 4)
        parent = course.products.get(structure=Product.PARENT)
        self.assertEqual(list(parent.categories.all()), [self.category])
        for seat in seats:
            seat_type = seat.attr.certificate_type
            if seat_type == 'professional' and not seat.attr.id_verification_required:
                seat_type = 'no-id-professional'
            logger.info('Validating objects for %s certificate type...', seat_type)

            stock_record = self.partner.stockrecords.get(product=seat)
            self.assert_seat_valid(seat, seat_type)
            self.assert_stock_record_valid(stock_record, seat, self.prices[seat_type])

    def assert_lms_api_headers(self, request):
        self.assertEqual(request.headers['Accept'], JSON)
        self.assertEqual(request.headers['Authorization'], 'Bearer ' + ACCESS_TOKEN)


class MigratedCourseTests(CourseMigrationTestMixin, TestCase):
    def _migrate_course_from_lms(self):
        """ Create a new MigratedCourse and simulate the loading of data from LMS. """
        self._mock_lms_api()
        migrated_course = MigratedCourse(self.course_id)
        migrated_course.load_from_lms(ACCESS_TOKEN)
        return migrated_course

    @httpretty.activate
    def test_load_from_lms(self):
        """ Verify the method creates new objects based on data loaded from the LMS. """
        migrated_course = self._migrate_course_from_lms()
        course = migrated_course.course

        # Ensure LMS was called with the correct headers
        for request in httpretty.httpretty.latest_requests:
            self.assert_lms_api_headers(request)

        # Verify created objects match mocked data
        parent_seat = course.parent_seat_product
        self.assertEqual(parent_seat.title, 'Seat in A Tést Côurse')

        for seat in course.seat_products:
            certificate_type = seat.attr.certificate_type
            if certificate_type == 'professional' and not seat.attr.id_verification_required:
                certificate_type = 'no-id-professional'
            logger.info('Validating objects for %s certificate type...', certificate_type)
            self.assert_stock_record_valid(seat.stockrecords.first(), seat, Decimal(self.prices[certificate_type]))


class CommandTests(CourseMigrationTestMixin, TestCase):
    @httpretty.activate
    def test_handle(self):
        """ Verify the management command retrieves data, but does not save it to the database. """
        initial_product_count = Product.objects.count()
        initial_stock_record_count = StockRecord.objects.count()

        self._mock_lms_api()
        call_command('migrate_course', self.course_id, access_token=ACCESS_TOKEN)

        # Ensure LMS was called with the correct headers
        for request in httpretty.httpretty.latest_requests:
            self.assert_lms_api_headers(request)

        self.assertEqual(Product.objects.count(), initial_product_count, 'No new Products should have been saved.')
        self.assertEqual(StockRecord.objects.count(), initial_stock_record_count,
                         'No new StockRecords should have been saved.')

    @httpretty.activate
    def test_handle_with_commit(self):
        """ Verify the management command retrieves data, and saves it to the database. """
        self._mock_lms_api()
        call_command('migrate_course', self.course_id, access_token=ACCESS_TOKEN, commit=True)
        self.assert_course_migrated()
