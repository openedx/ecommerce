import hashlib

import ddt
from django.core.cache import cache
import httpretty
import mock

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.services.course_discovery import get_course_catalogs
from ecommerce.services.tests.mixins import CourseDiscoveryMockMixin
from ecommerce.tests.testcases import TestCase


@ddt.ddt
@httpretty.activate
class CourseDiscoveryTests(CourseDiscoveryMockMixin, TestCase):

    def tearDown(self):
        # Reset HTTPretty state (clean up registered urls and request history)
        httpretty.reset()


    def _assert_num_requests(self, count):
        """
        DRY helper for verifying request counts.
        """
        self.assertEqual(len(httpretty.httpretty.latest_requests), count)

    def _assert_get_course_catalogs(self, catalog_name_list):
        """
        Helper method to validate the response from the method
        "get_course_catalogs".
        """
        cache_key = 'catalog.api.data'
        cache_key = hashlib.md5(cache_key).hexdigest()
        cached_course_catalogs = cache.get(cache_key)
        self.assertIsNone(cached_course_catalogs)

        response = get_course_catalogs(self.request.site)

        self.assertEqual(len(response), len(catalog_name_list))
        for catalog_index, catalog in enumerate(response):
            self.assertEqual(catalog['name'], catalog_name_list[catalog_index])

        cached_course = cache.get(cache_key)
        self.assertEqual(cached_course, response)

    @mock_course_catalog_api_client
    def test_get_course_catalogs_for_single_catalog_with_id(self):
        """
        Verify that method "get_course_catalogs" returns proper response for a
        single catalog by its id.
        """
        self.mock_course_discovery_api_for_catalog_by_resource_id()

        catalog_id = 1
        cache_key = 'catalog.api.data.{}'.format(catalog_id)
        cache_key = hashlib.md5(cache_key).hexdigest()
        cached_course_catalog = cache.get(cache_key)
        self.assertIsNone(cached_course_catalog)

        response = get_course_catalogs(self.request.site, catalog_id)

        self.assertEqual(response['count'], 1)
        self.assertEqual(response['results'][0]['name'], 'Catalog {}'.format(catalog_id))

        cached_course = cache.get(cache_key)
        self.assertEqual(cached_course, response)

        # Verify the API was actually hit (not the cache)
        self._assert_num_requests(1)

    @mock_course_catalog_api_client
    def test_get_course_catalogs_for_exception(self):
        """
        Verify that method "get_course_catalogs" returns empty list in
        response in case there is exception raised while accessing Course
        Discovery API.
        """
        self.mock_course_discovery_api_for_catalog_by_resource_id()

        catalog_id = 1
        cache_key = 'catalog.api.data.{}'.format(catalog_id)
        cache_key = hashlib.md5(cache_key).hexdigest()
        cached_course_catalog = cache.get(cache_key)
        self.assertIsNone(cached_course_catalog)

        response = get_course_catalogs(self.request.site, catalog_id)

        self.assertEqual(response['count'], 1)
        self.assertEqual(response['results'][0]['name'], 'Catalog {}'.format(catalog_id))

        cached_course = cache.get(cache_key)
        self.assertEqual(cached_course, response)

    @mock_course_catalog_api_client
    @ddt.data(
        ['Catalog 1'],
        ['Catalog 1', 'Catalog 2'],
    )
    def test_get_course_catalogs_for_single_page_api_response(self, catalog_name_list):
        """
        Verify that method "get_course_catalogs" returns proper response for
        single page Course Discovery API response and uses cache to return data
        in case of same API request.
        """
        self.mock_course_discovery_api_for_catalogs(catalog_name_list)

        self._assert_get_course_catalogs(catalog_name_list)

        # Verify the API was hit for once
        self._assert_num_requests(1)

        # Now fetch the catalogs again and there should be no more actual call
        # to Course Discovery API as the data will be fetched from the cache
        get_course_catalogs(self.request.site)
        self._assert_num_requests(1)

    @mock_course_catalog_api_client
    def test_get_course_catalogs_for_paginated_api_response(self):
        """
        Verify that method "get_course_catalogs" returns all catalogs for
        paginated Course Discovery API response for multiple catalogs.
        """
        catalog_name_list = ['Catalog 1', 'Catalog 2', 'Catalog 3']
        self.mock_course_discovery_api_for_paginated_catalogs(catalog_name_list)

        self._assert_get_course_catalogs(catalog_name_list)

        # Verify the API was hit for each catalog page
        self._assert_num_requests(len(catalog_name_list))

    @mock_course_catalog_api_client
    @mock.patch('ecommerce.services.course_discovery.logger.exception')
    def test_get_course_catalogs_for_failure(self, mock_exception):
        """
        Verify that method "get_course_catalogs" returns empty list in case
        the Course Discovery API fails to return data.
        """
        self.mock_course_discovery_api_for_failure()

        response = get_course_catalogs(self.request.site)

        self.assertTrue(mock_exception.called)
        self.assertEqual(response, [])
