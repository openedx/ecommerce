

import ddt
import httpretty
from django.conf import settings
from edx_django_utils.cache import TieredCache
from mock import patch
from oscar.core.loading import get_model
from oscar.test.factories import BasketFactory
from requests.exceptions import ConnectionError as ReqConnectionError

from ecommerce.core.tests import toggle_switch
from ecommerce.core.utils import get_cache_key
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise import api as enterprise_api
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.partner.strategy import DefaultStrategy
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')
StockRecord = get_model('partner', 'StockRecord')


@ddt.ddt
@httpretty.activate
class EnterpriseAPITests(EnterpriseServiceMockMixin, DiscoveryTestMixin, TestCase):
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

        self.basket = BasketFactory(site=self.site, owner=self.learner, strategy=self.request.strategy)

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

        enterprise_learner_cached_response = TieredCache.get_cached_response(cache_key)
        self.assertFalse(enterprise_learner_cached_response.is_found)

        response = enterprise_api.fetch_enterprise_learner_data(self.request.site, self.learner)
        self.assertEqual(len(response['results']), 1)

        course_cached_response = TieredCache.get_cached_response(cache_key)
        self.assertEqual(course_cached_response.value, response)

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

    def test_catalog_contains_course_runs_cache_hit(self):
        """
        Verify `catalog_contains_course_runs` returns a cached response
        """
        self.mock_catalog_contains_course_runs(
            [self.course_run.id],
            'fake-uuid',
            enterprise_customer_catalog_uuid=None,
            contains_content=True,
        )

        with patch.object(TieredCache, 'set_all_tiers', wraps=TieredCache.set_all_tiers) as mocked_set_all_tiers:
            mocked_set_all_tiers.assert_not_called()

            self._assert_contains_course_runs(True, [self.course_run.id], 'fake-uuid', None)
            self.assertEqual(mocked_set_all_tiers.call_count, 2)

            self._assert_contains_course_runs(True, [self.course_run.id], 'fake-uuid', None)
            self.assertEqual(mocked_set_all_tiers.call_count, 2)

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

        with self.assertRaises(ReqConnectionError):
            self._assert_contains_course_runs(False, [self.course_run.id], 'fake-uuid', 'fake-uuid')

    @patch('ecommerce.enterprise.api.fetch_enterprise_learner_data')
    @patch('ecommerce.enterprise.api.get_enterprise_id_for_current_request_user_from_jwt')
    def test_get_enterprise_id_for_user_fetch_learner_data_has_uuid(self, mock_get_jwt_uuid, mock_fetch):
        """
        Verify get_enterprise_id_for_user returns enterprise id if jwt does not have
        enterprise uuid, but is able to fetch it via api call
        """
        mock_get_jwt_uuid.return_value = None
        mock_fetch.return_value = {
            'results': [
                {
                    'enterprise_customer': {
                        'uuid': 'my-uuid'
                    }
                }
            ]
        }
        assert enterprise_api.get_enterprise_id_for_user('some-site', self.learner) == 'my-uuid'

    @patch('ecommerce.enterprise.api.fetch_enterprise_learner_data')
    @patch('ecommerce.enterprise.api.get_enterprise_id_for_current_request_user_from_jwt')
    def test_get_enterprise_id_for_user_fetch_errors(self, mock_get_jwt_uuid, mock_fetch):
        """
        Verify if that learner data fetch errors, get_enterprise_id_for_user
        returns None
        """
        mock_get_jwt_uuid.return_value = None
        mock_fetch.side_effect = [KeyError]

        assert enterprise_api.get_enterprise_id_for_user('some-site', self.learner) is None

    @patch('ecommerce.enterprise.api.fetch_enterprise_learner_data')
    @patch('ecommerce.enterprise.api.get_enterprise_id_for_current_request_user_from_jwt')
    def test_get_enterprise_id_for_user_no_uuid_in_response(self, mock_get_jwt_uuid, mock_fetch):
        """
        Verify if learner data fetch is successful but does not include uuid field,
        None is returned
        """
        mock_get_jwt_uuid.return_value = None
        mock_fetch.return_value = {
            'results': []
        }
        assert enterprise_api.get_enterprise_id_for_user('some-site', self.learner) is None
