
import ddt
import httpretty
from django.conf import settings
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberBaseException
from testfixtures import LogCapture

from ecommerce.core.tests import toggle_switch
from ecommerce.coupons.tests.mixins import CouponMixin, DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise.entitlements import (
    get_course_entitlements_for_learner,
    get_course_vouchers_for_learner,
    get_entitlement_voucher,
    is_course_in_enterprise_catalog
)
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.partner.strategy import DefaultStrategy
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')
StockRecord = get_model('partner', 'StockRecord')


@ddt.ddt
@httpretty.activate
class EntitlementsTests(EnterpriseServiceMockMixin, DiscoveryTestMixin, DiscoveryMockMixin,
                        CouponMixin, TestCase):
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

    def _assert_get_course_entitlements_for_learner_response(
            self, expected_entitlements, log_level, log_message, expected_request_count
    ):
        """
        Helper method to validate the response from the method
        "get_course_entitlements_for_learner" and verify the logged message.
        """
        logger_name = 'ecommerce.enterprise.entitlements'
        with LogCapture(logger_name) as logger:
            entitlements = get_course_entitlements_for_learner(
                self.request.site, self.request.user, self.course.id
            )
            self._assert_num_requests(expected_request_count)

            logger.check(
                (
                    logger_name,
                    log_level,
                    log_message
                )
            )
            self.assertEqual(expected_entitlements, entitlements)

    def _assert_is_course_in_enterprise_catalog_for_failure(self, expected_requests, log_message):
        """
        Helper method to validate the response from the method
        "is_course_in_enterprise_catalog" and verify the logged message.
        """
        enterprise_catalog_id = 1
        logger_name = 'ecommerce.enterprise.entitlements'
        with LogCapture(logger_name) as logger:
            is_course_available = is_course_in_enterprise_catalog(
                self.request.site, self.course.id, enterprise_catalog_id
            )
            self._assert_num_requests(expected_requests)

            logger.check(
                (
                    logger_name,
                    'ERROR',
                    log_message
                )
            )
            self.assertFalse(is_course_available)

    def _create_course_catalog_coupon(self, course_catalog_id=1, quantity=1):
        """
        Helper method to create course catalog coupon.
        """
        coupon_title = 'Course catalog coupon {}'.format(course_catalog_id)
        course_catalog_coupon = self.create_coupon(
            title=coupon_title,
            quantity=quantity,
            course_catalog=course_catalog_id,
            course_seat_types='verified'
        )
        return course_catalog_coupon

    def test_get_entitlement_voucher_with_enterprise_feature_disabled(self):
        """
        Verify that method "get_entitlement_voucher" doesn't call the
        enterprise service API and returns no voucher if the enterprise
        feature is disabled.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api()
        self.mock_enterprise_learner_entitlements_api()
        toggle_switch(settings.ENABLE_ENTERPRISE_ON_RUNTIME_SWITCH, False)

        entitlement_voucher = get_entitlement_voucher(self.request, self.course.products.first())
        self._assert_num_requests(0)
        self.assertIsNone(entitlement_voucher)

    def test_get_entitlement_voucher_with_enterprise_feature_enabled(self):
        """
        Verify that method "get_entitlement_voucher" returns a voucher if
        the enterprise feature is enabled.
        """
        self.mock_access_token_response()
        coupon = self.create_coupon(catalog=self.catalog)
        expected_voucher = coupon.attr.coupon_vouchers.vouchers.first()

        enterprise_catalog_id = 1
        self.mock_enterprise_learner_api(entitlement_id=coupon.id)
        self.mock_enterprise_learner_entitlements_api(entitlement_id=coupon.id)
        self.mock_catalog_contains_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, catalog_id=enterprise_catalog_id,
            course_run_ids=[self.course.id]
        )

        entitlement_voucher = get_entitlement_voucher(self.request, self.course.products.first())
        self._assert_num_requests(4)
        self.assertEqual(expected_voucher, entitlement_voucher)

    def test_get_entitlement_voucher_with_invalid_entitlement_id(self):
        """
        Verify that method "get_entitlement_voucher" logs exception if there
        is no coupon against the provided entitlement id in the enterprise
        learner API response.
        """
        non_existing_coupon_id = 99
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(
            catalog_id=non_existing_coupon_id, entitlement_id=non_existing_coupon_id
        )
        self.mock_enterprise_learner_entitlements_api(entitlement_id=non_existing_coupon_id)
        self.mock_catalog_contains_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, catalog_id=non_existing_coupon_id,
            course_run_ids=[self.course.id]
        )

        logger_name = 'ecommerce.enterprise.entitlements'
        with LogCapture(logger_name) as logger:
            entitlement_voucher = get_entitlement_voucher(self.request, self.course.products.first())
            self._assert_num_requests(4)

            logger.check(
                (
                    logger_name,
                    'ERROR',
                    'There was an error getting coupon product with the entitlement id %s' % non_existing_coupon_id
                )
            )
            self.assertIsNone(entitlement_voucher)

    def test_get_course_vouchers_for_learner_with_multiple_codes(self):
        """
        Verify that method "get_course_vouchers_for_learner" returns all valid
        coupon codes for the provided enterprise course.
        """
        catalog_id = 1
        coupon_quantity = 2
        coupon = self._create_course_catalog_coupon(catalog_id, coupon_quantity)
        expected_vouchers = coupon.attr.coupon_vouchers.vouchers.all()

        self.mock_access_token_response()
        self.mock_enterprise_learner_api(entitlement_id=coupon.id)
        self.mock_enterprise_learner_entitlements_api(entitlement_id=coupon.id)
        self.mock_catalog_contains_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, catalog_id=catalog_id,
            course_run_ids=[self.course.id]
        )
        course_vouchers = get_course_vouchers_for_learner(self.request.site, self.request.user, self.course.id)

        # Verify that there were total three calls. Two for getting
        # enterprise learner data and enterprise learner entitlements
        # from enterprise service and one for checking course run against
        # the enterprise catalog from the discovery service.
        self._assert_num_requests(4)
        self.assertEqual(coupon_quantity, len(course_vouchers))
        self.assertListEqual(list(expected_vouchers), list(course_vouchers))

    def test_get_course_vouchers_for_learner_with_exception(self):
        """
        Verify that method "get_course_vouchers_for_learner" returns empty
        response if there is an error while accessing the enterprise learner
        API.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api_for_failure()

        vouchers = get_course_vouchers_for_learner(self.request.site, self.request.user, self.course.id)
        self.assertIsNone(vouchers)

    def test_get_course_entitlements_for_learner_with_exception(self):
        """
        Verify that method "get_course_entitlements_for_learner" logs exception if
        there is an error while accessing the enterprise learner API.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api_for_failure()

        self._assert_get_course_entitlements_for_learner_response(
            expected_entitlements=None,
            log_level='ERROR',
            log_message='Failed to retrieve enterprise info for the learner [%s]' % self.learner.username,
            expected_request_count=2,
        )

    def test_learner_entitlements_with_exception(self):
        """
        Verify that method "get_course_entitlements_for_learner" logs exception if
        there is an error while accessing the learner entitlements.
        """
        learner_id = 1
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(learner_id=learner_id)
        self.mock_learner_entitlements_api_failure(learner_id=learner_id)
        self.mock_catalog_contains_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, course_run_ids=[self.course.id]
        )

        self._assert_get_course_entitlements_for_learner_response(
            expected_entitlements=None,
            log_level='ERROR',
            log_message='Failed to retrieve entitlements for enterprise learner [%s].' % learner_id,
            expected_request_count=4,
        )

    def test_learner_entitlements_invalid_response(self):
        """
        Verify that method "get_course_entitlements_for_learner" logs exception if
        there is an error while accessing the learner entitlements.
        """
        learner_id = 1
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(learner_id=learner_id)
        self.mock_learner_entitlements_api_failure(learner_id=learner_id, status=200)
        self.mock_catalog_contains_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, course_run_ids=[self.course.id]
        )

        self._assert_get_course_entitlements_for_learner_response(
            expected_entitlements=None,
            log_level='ERROR',
            log_message='Invalid structure for enterprise learner entitlements API response for enterprise learner'
                        ' [%s].' % learner_id,
            expected_request_count=4,
        )

    def test_get_course_entitlements_for_learner_with_no_enterprise(self):
        """
        Verify that method "get_course_entitlements_for_learner" logs and returns
        empty list if the learner is not affiliated with any enterprise.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api_for_learner_with_no_enterprise()

        self._assert_get_course_entitlements_for_learner_response(
            expected_entitlements=None,
            log_level='INFO',
            log_message='Learner with username [%s] in not affiliated with any enterprise' % self.learner.username,
            expected_request_count=2,
        )

    def test_get_course_entitlements_for_learner_with_invalid_response(self):
        """
        Verify that method "get_course_entitlements_for_learner" logs and returns
        empty list for entitlements if the enterprise learner API response has
        invalid/unexpected structure.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api_for_learner_with_invalid_response()

        message = 'Invalid structure for enterprise learner API response for the learner [%s]' % self.learner.username
        self._assert_get_course_entitlements_for_learner_response(
            expected_entitlements=None,
            log_level='ERROR',
            log_message=message,
            expected_request_count=2,
        )

    def test_get_course_entitlements_for_learner_with_invalid_entitlements_key_in_response(self):
        """
        Verify that method "get_course_entitlements_for_learner" logs and returns
        empty list for entitlements if the enterprise learner API response has
        invalid/unexpected or missing key for enterprise customer entitlements.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api_for_learner_with_invalid_entitlements_response()

        message = 'Invalid structure for enterprise learner API response for the learner [%s]' % self.learner.username
        self._assert_get_course_entitlements_for_learner_response(
            expected_entitlements=None,
            log_level='ERROR',
            log_message=message,
            expected_request_count=2,
        )

    def test_get_course_entitlements_for_learner_with_unavailable_course(self):
        """
        Verify that method "get_course_entitlements_for_learner" returns empty
        response for entitlements if the provided course id is not available
        in the related enterprise course catalog.
        """
        enterprise_catalog_id = 1
        self.mock_access_token_response()
        self.mock_enterprise_learner_api(entitlement_id=enterprise_catalog_id)
        self.mock_enterprise_learner_entitlements_api(entitlement_id=enterprise_catalog_id)
        self.mock_catalog_contains_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, catalog_id=enterprise_catalog_id,
            course_run_ids=[self.course.id]
        )

        non_enterprise_course = CourseFactory(id='edx/Non_Enterprise_Course/DemoX')
        entitlements = get_course_entitlements_for_learner(
            self.request.site, self.request.user, non_enterprise_course
        )
        # Verify that there were total two calls. First for getting
        # enterprise learner data from enterprise service and other one for
        # checking course run against the enterprise catalog query from the
        # discovery service.
        self._assert_num_requests(3)
        self.assertIsNone(entitlements)

    def test_is_course_in_enterprise_catalog_for_available_course(self):
        """
        Verify that method "is_course_in_enterprise_catalog" returns True if
        the provided course is available in the enterprise course catalog.
        """
        enterprise_catalog_id = 1
        self.mock_access_token_response()
        self.mock_catalog_contains_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, catalog_id=enterprise_catalog_id,
            course_run_ids=[self.course.id]
        )

        is_course_available = is_course_in_enterprise_catalog(self.request.site, self.course.id, enterprise_catalog_id)

        # Verify that there only one call for the course discovery API for
        # checking if course exists in course runs against the course catalog.
        self._assert_num_requests(2)
        self.assertTrue(is_course_available)

    def test_is_course_in_enterprise_catalog_for_unavailable_course(self):
        """
        Verify that method "is_course_in_enterprise_catalog" returns False if
        the provided course is not available in the enterprise course catalog.
        """
        enterprise_catalog_id = 1
        self.mock_access_token_response()
        self.mock_catalog_contains_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, catalog_id=enterprise_catalog_id,
            course_run_ids=[self.course.id]
        )

        test_course = CourseFactory(id='edx/Non_Enterprise_Course/DemoX')
        is_course_available = is_course_in_enterprise_catalog(self.request.site, test_course.id, enterprise_catalog_id)

        # Verify that there only one call for the course discovery API for
        # checking if course exists in course runs against the course catalog.
        self._assert_num_requests(2)
        self.assertFalse(is_course_available)

    @ddt.data(ConnectionError, SlumberBaseException, Timeout)
    def test_is_course_in_enterprise_catalog_for_error_in_get_course_catalogs(self, error):
        """
        Verify that method "is_course_in_enterprise_catalog" returns False
        and logs error message if the method "get_course_catalogs" is unable
        to fetch catalog against the provided enterprise course catalog id.
        """
        self.mock_access_token_response()
        self.mock_discovery_api_failure(error, self.site_configuration.discovery_api_url, 1)

        log_message = 'Unable to connect to Discovery Service for catalog contains endpoint.'
        self._assert_is_course_in_enterprise_catalog_for_failure(2, log_message)

    @ddt.data(ConnectionError, SlumberBaseException, Timeout)
    def test_is_course_in_enterprise_catalog_for_error_in_get_catalog_course_runs(self, error):
        """
        Verify that method "is_course_in_enterprise_catalog" returns False
        and logs error message if the method "is_course_in_catalog_query" is
        unable to validate the given course against the course runs for the
        provided enterprise catalog.
        """
        self.mock_access_token_response()
        self.mock_course_runs_contains_endpoint_failure(
            course_run_ids=[self.course.id], catalog_id=1, error=error,
            discovery_api_url=self.site_configuration.discovery_api_url
        )

        log_message = 'Unable to connect to Discovery Service for catalog contains endpoint.'
        self._assert_is_course_in_enterprise_catalog_for_failure(2, log_message)
