import httpretty
from django.conf import settings
from django.core.cache import cache
from oscar.core.loading import get_model

from ecommerce.core.tests import toggle_switch
from ecommerce.core.tests.decorators import mock_enterprise_api_client
from ecommerce.core.utils import get_cache_key
from ecommerce.enterprise import api as enterprise_api
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.partner.strategy import DefaultStrategy
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')
StockRecord = get_model('partner', 'StockRecord')


@httpretty.activate
class EnterpriseAPITests(EnterpriseServiceMockMixin, TestCase):
    def setUp(self):
        super(EnterpriseAPITests, self).setUp()
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

    @mock_enterprise_api_client
    def test_fetch_enterprise_learner_data(self):
        """
        Verify that method "fetch_enterprise_learner_data" returns a proper
        response for the enterprise learner.
        """
        self.mock_enterprise_learner_api()
        self._assert_fetch_enterprise_learner_data()

        # API should be hit only once in this test case
        expected_number_of_requests = 1

        # Verify the API was hit once
        self._assert_num_requests(expected_number_of_requests)

        # Now fetch the enterprise learner data again and verify that there was
        # no actual call to Enterprise API, as the data will be fetched from
        # the cache
        enterprise_api.fetch_enterprise_learner_data(self.request.site, self.learner)
        self._assert_num_requests(expected_number_of_requests)

    @mock_enterprise_api_client
    def test_fetch_enterprise_learner_entitlements(self):
        """
        Verify that method "fetch_enterprise_learner_data" returns a proper
        response for the enterprise learner.
        """
        # API should be hit only twice in this test case,
        # once by `fetch_enterprise_learner_data` and once by `fetch_enterprise_learner_entitlements`.
        expected_number_of_requests = 2

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
