import ddt
import httpretty
from django.conf import settings
from django.core.cache import cache
from oscar.core.loading import get_model

from ecommerce.core.tests import toggle_switch
from ecommerce.core.utils import get_cache_key
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise import api as enterprise_api
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.partner.strategy import DefaultStrategy
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')
StockRecord = get_model('partner', 'StockRecord')


@ddt.ddt
@httpretty.activate
class EnterpriseAPITests(EnterpriseServiceMockMixin, TestCase):
    def setUp(self):
        super(EnterpriseAPITests, self).setUp()
        self.course_run = CourseFactory()
        self.learner = self.create_user(is_staff=True)
        self.client.login(username=self.learner.username, password=self.password)

        # Enable enterprise functionality
        toggle_switch(settings.ENABLE_ENTERPRISE_ON_RUNTIME_SWITCH, True)

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

    def _assert_fetch_enterprise_learner_data(self):
        """
        Helper method to validate the response from the method
        "fetch_enterprise_learner_data".
        """
        cache_key = get_cache_key(
            site_domain=self.request.site.domain,
            partner_code=self.request.site.siteconfiguration.partner.short_code,
            resource='enterprise-learner',
            username=self.learner.username
        )

        cached_enterprise_learner_response = cache.get(cache_key)
        self.assertIsNone(cached_enterprise_learner_response)

        response = enterprise_api.fetch_enterprise_learner_data(self.request.site, self.learner)
        self.assertEqual(len(response['results']), 1)

        cached_course = cache.get(cache_key)
        self.assertEqual(cached_course, response)

    def _assert_contains_course_runs(self, expected, course_run_ids, enterprise_customer_uuid,
                                     enterprise_customer_catalog_uuid):
        """
        Helper method to validate the response from the method `catalog_contains_course_runs`.
        """
        actual = enterprise_api.catalog_contains_course_runs(
            self.site,
            course_run_ids,
            enterprise_customer_uuid,
            enterprise_customer_catalog_uuid=enterprise_customer_catalog_uuid,
        )

        self.assertEqual(expected, actual)

    def test_fetch_enterprise_learner_data(self):
        """
        Verify that method "fetch_enterprise_learner_data" returns a proper
        response for the enterprise learner.
        """
        self.mock_access_token_response()
        self.mock_enterprise_learner_api()
        self._assert_fetch_enterprise_learner_data()

        # API should be hit only once in this test case
        expected_number_of_requests = 2

        # Verify the API was hit once
        self._assert_num_requests(expected_number_of_requests)

        # Now fetch the enterprise learner data again and verify that there was
        # no actual call to Enterprise API, as the data will be fetched from
        # the cache
        enterprise_api.fetch_enterprise_learner_data(self.request.site, self.learner)
        self._assert_num_requests(expected_number_of_requests)

    def test_fetch_enterprise_learner_entitlements(self):
        """
        Verify that method "fetch_enterprise_learner_data" returns a proper
        response for the enterprise learner.
        """
        # API should be hit only twice in this test case,
        # once by `fetch_enterprise_learner_data` and once by `fetch_enterprise_learner_entitlements`.
        expected_number_of_requests = 3

        self.mock_access_token_response()
        self.mock_enterprise_learner_api()
        enterprise_learners = enterprise_api.fetch_enterprise_learner_data(self.request.site, self.learner)

        enterprise_learner_id = enterprise_learners['results'][0]['id']
        self.mock_enterprise_learner_entitlements_api(enterprise_learner_id)
        enterprise_api.fetch_enterprise_learner_entitlements(self.request.site, enterprise_learner_id)

        # Verify the API was hit just two times, once by `fetch_enterprise_learner_data`
        # and once by `fetch_enterprise_learner_entitlements`
        self._assert_num_requests(expected_number_of_requests)

        # Now fetch the enterprise learner entitlements again and verify that there was
        # no actual call to Enterprise API, as the data will be taken from
        # the cache
        enterprise_api.fetch_enterprise_learner_entitlements(self.request.site, enterprise_learner_id)
        self._assert_num_requests(expected_number_of_requests)

    @ddt.data(
        (True, None),
        (True, 'fake-uuid'),
        (False, None),
        (False, 'fake-uuid'),
    )
    @ddt.unpack
    def test_catalog_contains_course_runs(self, expected, enterprise_customer_catalog_uuid):
        """
        Verify that method `catalog_contains_course_runs` returns the appropriate response.
        """
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            'fake-uuid',
            enterprise_customer_catalog_uuid=enterprise_customer_catalog_uuid,
            contains_content=expected,
        )

        self._assert_contains_course_runs(expected, [self.course_run.id], 'fake-uuid', enterprise_customer_catalog_uuid)

    def test_catalog_contains_course_runs_with_api_exception(self):
        """
        Verify that method `catalog_contains_course_runs` returns the appropriate response
        when the Enterprise API cannot be reached.
        """
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            'fake-uuid',
            enterprise_customer_catalog_uuid='fake-uuid',
            contains_content=False,
            raise_exception=True,
        )

        self._assert_contains_course_runs(False, [self.course_run.id], 'fake-uuid', 'fake-uuid')
