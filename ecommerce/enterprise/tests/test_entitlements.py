import hashlib

import ddt
from django.core.cache import cache
from django.conf import settings
import httpretty
from oscar.core.loading import get_model
from testfixtures import LogCapture

from ecommerce.core.tests import toggle_switch
from ecommerce.core.tests.decorators import mock_enterprise_api_client
from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.coupons.tests.mixins import CouponMixin, CourseCatalogMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.courses.tests.mixins import CourseCatalogServiceMockMixin
from ecommerce.enterprise.entitlements import (
    get_enterprise_learner_data, get_entitlement_voucher, get_entitlements_for_learner,
    get_course_ids_from_voucher
)
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.partner.strategy import DefaultStrategy
from ecommerce.tests.testcases import TestCase


COURSE_CATALOG_API_URL = 'https://catalog.example.com/api/v1/'
Catalog = get_model('catalogue', 'Catalog')
StockRecord = get_model('partner', 'StockRecord')


@ddt.ddt
@httpretty.activate
class EntitlementsTests(EnterpriseServiceMockMixin, CourseCatalogServiceMockMixin, CourseCatalogTestMixin,
                        CourseCatalogMockMixin, CouponMixin, TestCase):
    def setUp(self):
        super(EntitlementsTests, self).setUp()
        self.learner = self.create_user(is_staff=True)
        self.client.login(username=self.learner.username, password=self.password)

        # Enable enterprise functionality
        toggle_switch(settings.ENABLE_ENTERPRISE_ON_RUNTIME_SWITCH, True)

        self.course = CourseFactory(id='edx/Demo_Course/DemoX')
        course_seat = self.course.create_or_update_seat('verified', False, 100, partner=self.partner)
        stock_record = StockRecord.objects.get(product=course_seat)
        self.catalog = Catalog.objects.create(partner=self.partner)
        self.catalog.stock_records.add(stock_record)

        self.request.user = self.learner
        self.request.site = self.site
        self.request.strategy = DefaultStrategy()

    def tearDown(self):
        # Reset HTTPretty state (clean up registered urls and request history)
        httpretty.reset()

    def _assert_num_requests(self, count):
        """
        DRY helper for verifying request counts.
        """
        self.assertEqual(len(httpretty.httpretty.latest_requests), count)

    def _create_course_catalog_coupon(self):
        """
        Helper method to create course catalog coupon.
        """
        coupon_title = 'Course catalog coupon'
        quantity = 1
        course_catalog_id = 1

        course_catalog_coupon = self.create_coupon(
            title=coupon_title,
            quantity=quantity,
            course_catalog=course_catalog_id,
        )
        course_catalog_coupon_voucher = course_catalog_coupon.attr.coupon_vouchers.vouchers.first()
        self.assertEqual(course_catalog_coupon.title, coupon_title)

        course_catalog_vouchers = course_catalog_coupon.attr.coupon_vouchers.vouchers.all()
        self.assertEqual(course_catalog_vouchers.count(), quantity)

        course_catalog_voucher_range = course_catalog_vouchers.first().offers.first().benefit.range
        self.assertEqual(course_catalog_voucher_range.course_catalog, course_catalog_id)

        return course_catalog_coupon_voucher

    def _create_multiple_course_coupon(self):
        """
        Helper method to multiple course (dynamic) coupon.
        """
        coupon_title = 'Multiple courses coupon'
        quantity = 1
        catalog_query = '*:*',
        course_seat_types = 'verified'

        course_catalog_coupon = self.create_coupon(
            title=coupon_title,
            quantity=quantity,
            catalog_query=catalog_query,
            course_seat_types=course_seat_types,
        )
        course_catalog_coupon_voucher = course_catalog_coupon.attr.coupon_vouchers.vouchers.first()
        self.assertEqual(course_catalog_coupon.title, coupon_title)

        course_catalog_vouchers = course_catalog_coupon.attr.coupon_vouchers.vouchers.all()
        self.assertEqual(course_catalog_vouchers.count(), quantity)

        course_catalog_voucher_range = course_catalog_vouchers.first().offers.first().benefit.range
        self.assertEqual(str(course_catalog_voucher_range.catalog_query), str(catalog_query))
        self.assertEqual(course_catalog_voucher_range.course_seat_types, course_seat_types)

        return course_catalog_coupon_voucher

    def _assert_get_enterprise_learner_data(self):
        """
        Helper method to validate the response from the method
        "get_enterprise_learner_data".
        """
        api_resource_name = 'enterprise-learner'
        partner_code = self.request.site.siteconfiguration.partner.short_code
        cache_key = '{site_domain}_{partner_code}_{resource}_{username}'.format(
            site_domain=self.request.site.domain,
            partner_code=partner_code,
            resource=api_resource_name,
            username=self.learner.username
        )
        cache_key = hashlib.md5(cache_key).hexdigest()

        cached_enterprise_learner_response = cache.get(cache_key)
        self.assertIsNone(cached_enterprise_learner_response)

        response = get_enterprise_learner_data(self.request.site, self.learner)
        self.assertEqual(len(response['results']), 1)

        cached_course = cache.get(cache_key)
        self.assertEqual(cached_course, response)

    def _assert_get_entitlements_for_learner_log_and_response(self, expected_entitlements, log_level, log_message):
        """
        Helper method to validate the response from the method
        "get_entitlements_for_learner" and verify the logged message.
        """
        logger_name = 'ecommerce.enterprise.entitlements'
        with LogCapture(logger_name) as logger:
            entitlements = get_entitlements_for_learner(self.request.site, self.request.user)
            self._assert_num_requests(1)

            logger.check(
                (
                    logger_name,
                    log_level,
                    log_message
                )
            )
            self.assertEqual(expected_entitlements, entitlements)

    def _assert_get_course_ids_from_voucher_for_failure(self, voucher, expected_requests, log_message):
        """
        Helper method to validate the response from the method
        "get_course_ids_from_voucher" and verify the logged message.
        """
        logger_name = 'ecommerce.enterprise.entitlements'
        with LogCapture(logger_name) as logger:
            voucher_course_ids = get_course_ids_from_voucher(self.request.site, voucher)
            self._assert_num_requests(expected_requests)
            logger.check(
                (
                    logger_name,
                    'ERROR',
                    log_message
                )
            )
            self.assertEqual(None, voucher_course_ids)

    @mock_enterprise_api_client
    def test_get_enterprise_learner_data(self):
        """
        Verify that method "get_enterprise_learner_data" returns a proper
        response for the enterprise learner.
        """
        self.mock_enterprise_learner_api()
        self._assert_get_enterprise_learner_data()

        # Verify the API was hit once
        self._assert_num_requests(1)

        # Now fetch the enterprise learner data again and verify that was no
        # actual call to Enterprise API, as the data will be fetched from the
        # cache
        get_enterprise_learner_data(self.request.site, self.learner)
        self._assert_num_requests(1)

    @mock_enterprise_api_client
    def test_get_entitlement_voucher_with_enterprise_feature_disabled(self):
        """
        Verify that method "get_entitlement_voucher" doesn't call the
        enterprise service API and returns no voucher if the enterprise
        feature is disabled.
        """
        self.mock_enterprise_learner_api()
        toggle_switch(settings.ENABLE_ENTERPRISE_ON_RUNTIME_SWITCH, False)

        entitlement_voucher = get_entitlement_voucher(self.request, self.course.products.first())
        self._assert_num_requests(0)
        self.assertIsNone(entitlement_voucher)

    @mock_enterprise_api_client
    def test_get_entitlement_voucher_with_enterprise_feature_enabled(self):
        """
        Verify that method "get_entitlement_voucher" returns a voucher if
        the enterprise feature is enabled.
        """
        coupon = self.create_coupon(catalog=self.catalog)
        expected_voucher = coupon.attr.coupon_vouchers.vouchers.first()

        self.mock_enterprise_learner_api(entitlement_id=coupon.id)

        entitlement_voucher = get_entitlement_voucher(self.request, self.course.products.first())
        self._assert_num_requests(1)
        self.assertEqual(expected_voucher, entitlement_voucher)

    @mock_enterprise_api_client
    def test_get_entitlement_voucher_with_invalid_entitlement_id(self):
        """
        Verify that method "get_entitlement_voucher" logs exception if there
        is no coupon against the provided entitlement id in the enterprise
        learner API response.
        """
        non_existing_coupon_id = 99
        self.mock_enterprise_learner_api(entitlement_id=non_existing_coupon_id)

        logger_name = 'ecommerce.enterprise.entitlements'
        with LogCapture(logger_name) as logger:
            entitlement_voucher = get_entitlement_voucher(self.request, self.course.products.first())
            self._assert_num_requests(1)

            logger.check(
                (
                    logger_name,
                    'ERROR',
                    'There was an error getting coupon product with the entitlement id %s' % non_existing_coupon_id
                )
            )
            self.assertIsNone(entitlement_voucher)

    @mock_enterprise_api_client
    def test_get_entitlements_for_learner_with_exception(self):
        """
        Verify that method "get_entitlements_for_learner" logs exception if
        there is an error while accessing the enterprise learner API.
        """
        self.mock_enterprise_learner_api_for_failure()

        self._assert_get_entitlements_for_learner_log_and_response(
            expected_entitlements=None,
            log_level='ERROR',
            log_message='Failed to retrieve enterprise info for the learner [%s]' % self.learner.username,
        )

    @mock_enterprise_api_client
    def test_get_entitlements_for_learner_with_no_enterprise(self):
        """
        Verify that method "get_entitlements_for_learner" logs and returns
        empty list if the learner is not affiliated with any enterprise.
        """
        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()

        self._assert_get_entitlements_for_learner_log_and_response(
            expected_entitlements=None,
            log_level='INFO',
            log_message='Learner with username [%s] in not affiliated with any enterprise' % self.learner.username,
        )

    @mock_enterprise_api_client
    def test_get_entitlements_for_learner_with_invalid_response(self):
        """
        Verify that method "get_entitlements_for_learner" logs and returns
        empty list for entitlements if the enterprise learner API response has
        invalid/unexpected structure.
        """
        self.mock_enterprise_learner_api_for_learner_with_invalid_response()

        message = 'Invalid structure for enterprise learner API response for the learner [%s]' % self.learner.username
        self._assert_get_entitlements_for_learner_log_and_response(
            expected_entitlements=None,
            log_level='ERROR',
            log_message=message
        )

    @mock_course_catalog_api_client
    def test_get_course_ids_from_voucher_for_catalog_voucher(self):
        """
        Verify that method "get_course_ids_from_voucher" returns course ids
        related to a course catalog voucher.
        """
        course_catalog_coupon_voucher = self._create_course_catalog_coupon()

        catalog_query = '*:*'
        self.mock_course_discovery_api_for_catalog_by_resource_id(catalog_query=catalog_query)
        partner_code = self.request.site.siteconfiguration.partner.short_code
        self.mock_dynamic_catalog_course_runs_api(
            course_run=self.course, partner_code=partner_code, query=catalog_query
        )

        voucher_course_ids = get_course_ids_from_voucher(self.request.site, course_catalog_coupon_voucher)
        # Verify that there were two calls for the course discovery API, one
        # for getting all course_catalogs and the other for getting course
        # runs against the course catalog query
        self._assert_num_requests(2)

        expected_voucher_course_ids = [self.course.id]
        self.assertEqual(expected_voucher_course_ids, voucher_course_ids)

    @mock_course_catalog_api_client
    def test_get_course_ids_from_voucher_for_error_in_get_course_catalogs(self):
        """
        Verify that method "get_course_ids_from_voucher" returns empty course ids
        if get_course_catalogs raises exception.
        """
        course_catalog_coupon_voucher = self._create_course_catalog_coupon()

        self.mock_course_discovery_api_for_failure()
        # Verify that there was only one call to the course discovery API and
        # it fails with error
        self._assert_get_course_ids_from_voucher_for_failure(
            voucher=course_catalog_coupon_voucher,
            expected_requests=1,
            log_message='Unable to connect to Course Catalog service for course catalogs.'
        )

    @mock_course_catalog_api_client
    def test_get_course_ids_from_voucher_for_error_in_get_catalog_course_runs(self):
        """
        Verify that method "get_course_ids_from_voucher" returns empty course ids
        if get_catalog_course_runs raises exception.
        """
        course_catalog_coupon_voucher = self._create_course_catalog_coupon()

        self.mock_course_discovery_api_for_catalog_by_resource_id()
        self.mock_course_discovery_api_for_failure()
        # Verify that there was two calls to the course discovery API, one for
        # getting details of course catalog and other for getting course run
        # against the catalog query and it fails with error
        self._assert_get_course_ids_from_voucher_for_failure(
            voucher=course_catalog_coupon_voucher,
            expected_requests=2,
            log_message='Unable to get course runs from Course Catalog service.'
        )

    @mock_course_catalog_api_client
    def test_get_course_ids_from_voucher_for_dynamic_voucher(self):
        """
        Verify that method "get_course_ids_from_voucher" returns course ids
        related to a dynamic catalog voucher query.
        """
        coupon_title = 'Multiple courses coupon'
        quantity = 1
        catalog_query = '*:*',
        course_seat_types = 'verified'

        course_catalog_coupon = self.create_coupon(
            title=coupon_title,
            quantity=quantity,
            catalog_query=catalog_query,
            course_seat_types=course_seat_types,
        )
        course_catalog_coupon_voucher = course_catalog_coupon.attr.coupon_vouchers.vouchers.first()
        self.assertEqual(course_catalog_coupon.title, coupon_title)

        course_catalog_vouchers = course_catalog_coupon.attr.coupon_vouchers.vouchers.all()
        self.assertEqual(course_catalog_vouchers.count(), quantity)

        course_catalog_voucher_range = course_catalog_vouchers.first().offers.first().benefit.range
        self.assertEqual(str(course_catalog_voucher_range.catalog_query), str(catalog_query))
        self.assertEqual(course_catalog_voucher_range.course_seat_types, course_seat_types)

        partner_code = self.request.site.siteconfiguration.partner.short_code
        self.mock_dynamic_catalog_course_runs_api(
            course_run=self.course, partner_code=partner_code, query=catalog_query
        )

        voucher_course_ids = get_course_ids_from_voucher(self.request.site, course_catalog_coupon_voucher)
        # Verify that there was only one call to the course discovery API for
        # getting course runs against the catalog query from dynamic coupon.
        self._assert_num_requests(1)

        expected_voucher_course_ids = [self.course.id]
        self.assertEqual(expected_voucher_course_ids, voucher_course_ids)

    @mock_course_catalog_api_client
    def test_get_course_ids_from_dynamic_voucher_for_error_in_get_catalog_course_runs(self):
        """
        Verify that method "get_course_ids_from_voucher" returns empty course
        ids if get_course_ids_from_voucher raises exception for getting course
        runs from course discovery service.
        """
        course_catalog_coupon_voucher = self._create_multiple_course_coupon()
        self.mock_course_discovery_api_for_failure()
        # Verify that there was only one call to the course discovery API for
        # course runs and it fails with error
        self._assert_get_course_ids_from_voucher_for_failure(
            voucher=course_catalog_coupon_voucher,
            expected_requests=1,
            log_message='Unable to get course runs from Course Catalog service.'
        )
