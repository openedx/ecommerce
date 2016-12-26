import json

import ddt
import httpretty
from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import RequestFactory
import mock
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError, Timeout
from slumber.exceptions import SlumberBaseException

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.coupons.tests.mixins import CourseCatalogMockMixin
from ecommerce.courses.tests.mixins import CourseCatalogServiceMockMixin
from ecommerce.extensions.api.serializers import ProductSerializer
from ecommerce.extensions.api.v2.tests.views.mixins import CatalogMixin
from ecommerce.extensions.api.v2.views.catalog import CatalogViewSet
from ecommerce.tests.mixins import ApiMockMixin
from ecommerce.tests.testcases import TestCase


Catalog = get_model('catalogue', 'Catalog')
StockRecord = get_model('partner', 'StockRecord')


@httpretty.activate
@ddt.ddt
class CatalogViewSetTest(CatalogMixin, CourseCatalogMockMixin, CourseCatalogServiceMockMixin, ApiMockMixin, TestCase):
    """Test the Catalog and related products APIs."""

    catalog_list_path = reverse('api:v2:catalog-list')

    def setUp(self):
        super(CatalogViewSetTest, self).setUp()

        self.client.login(username=self.user.username, password=self.password)

    def prepare_request(self, url):
        factory = RequestFactory()
        request = factory.get(url)
        request.site = self.site
        return request

    def test_staff_authorization_required(self):
        """Verify that only users with staff permissions can access the API. """
        response = self.client.get(self.catalog_list_path)

        self.assertEqual(response.status_code, 200)
        self.client.logout()

        response = self.client.get(self.catalog_list_path)
        self.assertEqual(response.status_code, 401)

    def test_authentication_required(self):
        """Verify that the unauthenticated users don't have access to the API"""
        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)

        response = self.client.get(self.catalog_list_path)
        self.assertEqual(response.status_code, 403)

    def test_catalog_list(self):
        """Verify the endpoint returns all catalogs."""
        response = self.client.get(self.catalog_list_path)
        expected_data = self.serialize_catalog(self.catalog)
        response_data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['count'], 1)
        self.assertListEqual(response_data['results'], [expected_data])

    def test_catalog_detail(self):
        """ Verify the view returns a single catalog details. """
        # The view should return a 404 if the catalog does not exist.
        path = reverse('api:v2:catalog-detail', kwargs={'pk': 'abc'})
        response = self.client.get(path)
        self.assertEqual(response.status_code, 404)

        path = reverse('api:v2:catalog-detail', kwargs={'pk': self.catalog.id})
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(json.loads(response.content), self.serialize_catalog(self.catalog))

    def test_catalog_products(self):
        """Verify the endpoint returns all products associated with a specific catalog."""
        path = reverse(
            'api:v2:catalog-product-list',
            kwargs={'parent_lookup_stockrecords__catalogs': self.catalog.id}
        )
        response = self.client.get(path)
        response_data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['count'], 0)
        self.assertListEqual(response_data['results'], [])

        self.catalog.stock_records.add(self.stock_record)

        response = self.client.get(path)
        response_data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['count'], 1)

        expected_data = ProductSerializer(self.stock_record.product, context={'request': response.wsgi_request}).data
        self.assertListEqual(response_data['results'], [expected_data])

    @ddt.data(
        ('/api/v2/coupons/preview/', 400),
        ('/api/v2/coupons/preview/?query=', 400),
        ('/api/v2/coupons/preview/?wrong=parameter', 400),
        ('/api/v2/coupons/preview/?query=id:course*', 400),
        ('/api/v2/coupons/preview/?query=id:course*&seat_types=verified', 200),
    )
    @ddt.unpack
    @mock_course_catalog_api_client
    def test_preview_catalog_query_results(self, url, status_code):
        """Test catalog query preview."""
        self.mock_dynamic_catalog_course_runs_api()

        request = self.prepare_request(url)
        response = CatalogViewSet().preview(request)

        self.assertEqual(response.status_code, status_code)

    @ddt.data(ConnectionError, SlumberBaseException, Timeout)
    @mock_course_catalog_api_client
    def test_preview_catalog_course_discovery_service_not_available(self, error):
        """Test catalog query preview when course discovery is not available."""
        url = '/api/v2/coupons/preview/?query=id:course*'
        request = self.prepare_request(url)

        self.mock_api_error(error=error, url='{}course_runs/?q=id:course*'.format(settings.COURSE_CATALOG_API_URL))

        response = CatalogViewSet().preview(request)
        self.assertEqual(response.status_code, 400)

    @ddt.data(
        (
            '/api/v2/coupons/course_catalogs/',
            ['Catalog 1'],
            ['Catalog 1']
        ),
        (
            '/api/v2/coupons/course_catalogs/',
            ['Clean Catalog', 'ABC Catalog', 'New Catalog', 'Edx Catalog'],
            ['ABC Catalog', 'Clean Catalog', 'Edx Catalog', 'New Catalog']
        ),
    )
    @ddt.unpack
    @mock_course_catalog_api_client
    def test_course_catalogs_for_single_page_api_response(self, url, catalog_name_list, sorted_catalog_name_list):
        """
        Test course catalogs list view "course_catalogs" for valid response
        with catalogs in alphabetical order.
        """
        self.mock_course_discovery_api_for_catalogs(catalog_name_list)

        request = self.prepare_request(url)
        response = CatalogViewSet().course_catalogs(request)

        self.assertEqual(response.status_code, 200)
        # Validate that the catalogs are sorted by name in alphabetical order
        self._assert_get_course_catalogs_response_with_order(response, sorted_catalog_name_list)

    def _assert_get_course_catalogs_response_with_order(self, response, catalog_name_list):
        """
        Helper method to validate the response from the method
        "course_catalogs".
        """
        response_results = response.data.get('results')
        self.assertEqual(len(response_results), len(catalog_name_list))
        for catalog_index, catalog in enumerate(response_results):
            self.assertEqual(catalog['name'], catalog_name_list[catalog_index])

    @mock_course_catalog_api_client
    @mock.patch('ecommerce.extensions.api.v2.views.catalog.logger.exception')
    def test_get_course_catalogs_for_failure(self, mock_exception):
        """
        Verify that the course catalogs list view "course_catalogs" returns
        empty results list in case the Course Discovery API fails to return
        data.
        """
        self.mock_course_discovery_api_for_failure()

        request = self.prepare_request('/api/v2/coupons/course_catalogs/')
        response = CatalogViewSet().course_catalogs(request)

        self.assertTrue(mock_exception.called)
        self.assertEqual(response.data.get('results'), [])


class PartnerCatalogViewSetTest(CatalogMixin, TestCase):
    def setUp(self):
        super(PartnerCatalogViewSetTest, self).setUp()

        self.client.login(username=self.user.username, password=self.password)

        self.catalog.stock_records.add(self.stock_record)

        # URL for getting catalog for partner.
        self.url = reverse(
            'api:v2:partner-catalogs-list',
            kwargs={'parent_lookup_partner_id': self.partner.id},
        )

    def test_get_partner_catalogs(self):
        """Verify the endpoint returns all catalogs associated with a specific partner."""
        response = self.client.get(self.url)
        expected_data = self.serialize_catalog(self.catalog)
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(json.loads(response.content)['results'], [expected_data])

    def test_staff_authorization_catalog_api(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        self.client.logout()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_authentication_catalog_api(self):
        """Verify only staff users can access the endpoint."""

        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_no_partner_catalog(self):
        """Verify the endpoint returns an empty result set if the partner has
        no associated catalogs.
        """
        Catalog.objects.filter(name='dummy', partner=self.partner).delete()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        expected = {
            'count': 0,
            'next': None,
            'previous': None,
            'results': []
        }
        self.assertDictEqual(json.loads(response.content), expected)
