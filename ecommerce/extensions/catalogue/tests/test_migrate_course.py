# coding=utf-8


import datetime
import json
import logging
from decimal import Decimal
from urllib.parse import urlparse

import httpretty
import mock
import pytz
from django.core.management import call_command
from django.test import override_settings
from oscar.core.loading import get_model
from testfixtures import LogCapture

from ecommerce.core.constants import ISO_8601_FORMAT
from ecommerce.core.tests import toggle_switch
from ecommerce.courses.models import Course
from ecommerce.courses.publishers import LMSPublisher
from ecommerce.courses.utils import mode_for_product
from ecommerce.extensions.catalogue.management.commands.migrate_course import MigratedCourse
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.catalogue.utils import generate_sku
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'
EDX_API_KEY = ACCESS_TOKEN = 'edx'
EXPIRES = datetime.datetime(year=1985, month=10, day=26, hour=1, minute=20, tzinfo=pytz.utc)
EXPIRES_STRING = EXPIRES.strftime(ISO_8601_FORMAT)

LOGGER_NAME = 'ecommerce.extensions.catalogue.management.commands.migrate_course'
logger = logging.getLogger(__name__)

Category = get_model('catalogue', 'Category')
Product = get_model('catalogue', 'Product')
StockRecord = get_model('partner', 'StockRecord')


class CourseMigrationTestMixin(DiscoveryTestMixin):
    course_id = 'aaa/bbb/ccc'
    course_name = 'A Tést Côurse'

    prices = {
        'honor': 0,
        'verified': 10,
        'professional': 1000,
        'audit': 0,
        'credit': 0,
    }

    @property
    def commerce_api_url(self):
        return self.site_configuration.build_lms_url('/api/commerce/v1/courses/{}/'.format(self.course_id))

    @property
    def course_structure_url(self):
        return self.site_configuration.build_lms_url('/api/course_structure/v0/courses/{}/'.format(self.course_id))

    @property
    def enrollment_api_url(self):
        return self.site_configuration.build_lms_url('/api/enrollment/v1/course/{}'.format(self.course_id))

    def _mock_lms_apis(self):
        self.assertTrue(httpretty.is_enabled(), 'httpretty must be enabled to mock LMS API calls.')

        # Mock Commerce API
        body = {
            'name': self.course_name,
            'verification_deadline': EXPIRES_STRING,
        }
        httpretty.register_uri(httpretty.GET, self.commerce_api_url, body=json.dumps(body), content_type=JSON)

        # Mock Course Structure API
        body = {'name': self.course_name}
        httpretty.register_uri(httpretty.GET, self.course_structure_url, body=json.dumps(body), content_type=JSON)

        # Mock Enrollment API
        body = {
            'course_id': self.course_id,
            'course_modes': [{'slug': mode, 'min_price': price, 'expiration_datetime': EXPIRES_STRING} for
                             mode, price in self.prices.items()]
        }
        httpretty.register_uri(httpretty.GET, self.enrollment_api_url, body=json.dumps(body), content_type=JSON)

    def assert_stock_record_valid(self, stock_record, seat, price):
        """ Verify the given StockRecord is configured correctly. """
        self.assertEqual(stock_record.partner, self.partner)
        self.assertEqual(stock_record.price_excl_tax, price)
        self.assertEqual(stock_record.price_currency, 'USD')
        self.assertEqual(stock_record.partner_sku, generate_sku(seat, self.partner))

    def assert_seat_valid(self, seat, mode):
        """ Verify the given seat is configured correctly. """
        certificate_type = Course.certificate_type_for_mode(mode)

        expected_title = 'Seat in {}'.format(self.course_name)
        if certificate_type != '':
            expected_title += ' with {} certificate'.format(certificate_type)

            if seat.attr.id_verification_required:
                expected_title += u' (and ID verification)'

        self.assertEqual(seat.title, expected_title)
        self.assertEqual(getattr(seat.attr, 'certificate_type', ''), certificate_type)
        self.assertEqual(seat.expires, EXPIRES)
        self.assertEqual(seat.attr.course_key, self.course_id)
        self.assertEqual(seat.attr.id_verification_required, Course.is_mode_verified(mode))

    def assert_course_migrated(self):
        """ Verify the course was migrated and saved to the database. """
        course = Course.objects.get(id=self.course_id)
        seats = course.seat_products

        # Verify that all modes are migrated.
        self.assertEqual(len(seats), len(self.prices))

        parent = course.products.get(structure=Product.PARENT)
        self.assertEqual(list(parent.categories.all()), [self.category])

        for seat in seats:
            mode = mode_for_product(seat)
            logger.info('Validating objects for [%s] mode...', mode)

            stock_record = self.partner.stockrecords.get(product=seat)
            self.assert_seat_valid(seat, mode)
            self.assert_stock_record_valid(stock_record, seat, self.prices[mode])


@override_settings(EDX_API_KEY=EDX_API_KEY)
class MigratedCourseTests(CourseMigrationTestMixin, TestCase):
    def setUp(self):
        super(MigratedCourseTests, self).setUp()
        toggle_switch('publish_course_modes_to_lms', True)
        httpretty.enable()
        self.mock_access_token_response()

    def tearDown(self):
        super(MigratedCourseTests, self).tearDown()
        httpretty.disable()
        httpretty.reset()

    def _migrate_course_from_lms(self):
        """ Create a new MigratedCourse and simulate the loading of data from LMS. """
        self._mock_lms_apis()
        migrated_course = MigratedCourse(self.course_id, self.site.domain)
        migrated_course.load_from_lms()
        return migrated_course

    def test_load_from_lms(self):
        """ Verify the method creates new objects based on data loaded from the LMS. """
        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            mock_publish.return_value = True
            migrated_course = self._migrate_course_from_lms()
            course = migrated_course.course

            # Verify that the migrated course was not published back to the LMS
            self.assertFalse(mock_publish.called)

        # Verify created objects match mocked data
        parent_seat = course.parent_seat_product
        self.assertEqual(parent_seat.title, 'Seat in {}'.format(self.course_name))
        self.assertEqual(course.verification_deadline, EXPIRES)

        for seat in course.seat_products:
            mode = mode_for_product(seat)
            logger.info('Validating objects for [%s] mode...', mode)

            self.assert_stock_record_valid(seat.stockrecords.first(), seat, Decimal(self.prices[mode]))

    def test_course_name_missing(self):
        """Verify the Course Structure API is queried if the Commerce API doesn't return a course name."""
        # Mock the Commerce API so that it does not return a name
        body = {
            'name': None,
            'verification_deadline': EXPIRES_STRING,
        }
        httpretty.register_uri(httpretty.GET, self.commerce_api_url, body=json.dumps(body), content_type=JSON)

        # Mock the Course Structure API
        httpretty.register_uri(httpretty.GET, self.course_structure_url, body='{}', content_type=JSON)

        # Try migrating the course, which should fail.
        try:
            migrated_course = MigratedCourse(self.course_id, self.site.domain)
            migrated_course.load_from_lms()
        except Exception as ex:  # pylint: disable=broad-except
            self.assertEqual(str(ex),
                             'Aborting migration. No name is available for {}.'.format(self.course_id))

        # Verify the Course Structure API was called.
        last_request = httpretty.last_request()
        self.assertEqual(last_request.path, urlparse(self.course_structure_url).path)

    def test_fall_back_to_course_structure(self):
        """
        Verify that migration falls back to the Course Structure API when data is unavailable from the Commerce API.
        """
        self._mock_lms_apis()

        body = {'detail': 'Not found'}
        httpretty.register_uri(
            httpretty.GET,
            self.commerce_api_url,
            status=404,
            body=json.dumps(body),
            content_type=JSON
        )

        migrated_course = MigratedCourse(self.course_id, self.site.domain)
        migrated_course.load_from_lms()
        course = migrated_course.course

        # Verify that created objects match mocked data.
        parent_seat = course.parent_seat_product
        self.assertEqual(parent_seat.title, 'Seat in {}'.format(self.course_name))
        # Confirm that there is no verification deadline set for the course.
        self.assertEqual(course.verification_deadline, None)

        for seat in course.seat_products:
            mode = mode_for_product(seat)
            self.assert_stock_record_valid(seat.stockrecords.first(), seat, Decimal(self.prices[mode]))

    def test_whitespace_stripped(self):
        """Verify that whitespace in course names is stripped during migration."""
        self._mock_lms_apis()

        body = {
            # Wrap the course name with whitespace
            'name': '  {}  '.format(self.course_name),
            'verification_deadline': EXPIRES_STRING,
        }
        httpretty.register_uri(httpretty.GET, self.commerce_api_url, body=json.dumps(body), content_type=JSON)

        migrated_course = MigratedCourse(self.course_id, self.site.domain)
        migrated_course.load_from_lms()
        course = migrated_course.course

        # Verify that whitespace has been stripped from the course name.
        self.assertEqual(course.name, self.course_name)

        parent_seat = course.parent_seat_product
        self.assertEqual(parent_seat.title, 'Seat in {}'.format(self.course_name))


@override_settings(EDX_API_KEY=EDX_API_KEY)
class CommandTests(CourseMigrationTestMixin, TestCase):
    def setUp(self):
        super(CommandTests, self).setUp()
        toggle_switch('publish_course_modes_to_lms', True)

    @httpretty.activate
    def test_handle(self):
        """ Verify the management command retrieves data, but does not save it to the database. """
        initial_product_count = Product.objects.count()
        initial_stock_record_count = StockRecord.objects.count()

        self._mock_lms_apis()

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            mock_publish.return_value = True
            call_command(
                'migrate_course', self.course_id, site_domain=self.site.domain
            )

            # Verify that the migrated course was not published back to the LMS
            self.assertFalse(mock_publish.called)

        self.assertEqual(Product.objects.count(), initial_product_count, 'No new Products should have been saved.')
        self.assertEqual(StockRecord.objects.count(), initial_stock_record_count,
                         'No new StockRecords should have been saved.')

    @httpretty.activate
    def test_handle_with_commit(self):
        """ Verify the management command retrieves data, and saves it to the database. """
        self.mock_access_token_response()
        self._mock_lms_apis()

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            call_command(
                'migrate_course',
                self.course_id,
                commit=True,
                # `site_domain` is the option destination variable
                site_domain=self.site.domain
            )

            # Verify that the migrated course was published back to the LMS
            self.assertTrue(mock_publish.called)

        self.assert_course_migrated()

    @httpretty.activate
    def test_handle_with_no_site(self):
        """ Verify the management command does not run if no site domain is provided. """
        self._mock_lms_apis()

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            with LogCapture(LOGGER_NAME, level=logging.ERROR) as captured_logger:
                call_command(
                    'migrate_course',
                    self.course_id,
                    commit=True
                )

                captured_logger.check((
                    LOGGER_NAME,
                    'ERROR',
                    'Courses cannot be migrated without providing a site domain.'
                ))
                # Verify that the migrated course was published back to the LMS
                self.assertFalse(mock_publish.called)

    @httpretty.activate
    def test_handle_with_commit_false(self):
        """ Verify the management command does not save data to the database if commit is false"""
        self._mock_lms_apis()

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            call_command(
                'migrate_course',
                self.course_id,
                commit=False,
                site=self.site.domain
            )

            # Verify that the migrated course was published back to the LMS
            self.assertFalse(mock_publish.called)

    @httpretty.activate
    def test_handle_with_false_switch(self):
        """ Verify the management command does not save data to the database if commit is false"""
        self._mock_lms_apis()
        toggle_switch('publish_course_modes_to_lms', False)

        with mock.patch.object(LMSPublisher, 'publish') as mock_publish:
            call_command(
                'migrate_course',
                self.course_id,
                commit=True,
                site=self.site.domain
            )

            # Verify that the migrated course was published back to the LMS
            self.assertFalse(mock_publish.called)
