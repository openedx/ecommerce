

import ddt
import httpretty
import mock
from django.urls import reverse
from oscar.core.loading import get_model
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from slumber.exceptions import SlumberBaseException

from ecommerce.coupons.tests.mixins import DiscoveryMockMixin
from ecommerce.extensions.api.serializers import ProductSerializer
from ecommerce.extensions.api.v2.tests.views.mixins import CatalogMixin
from ecommerce.tests.factories import PartnerFactory
from ecommerce.tests.mixins import ApiMockMixin
from ecommerce.tests.testcases import TestCase

Catalog = get_model('catalogue', 'Catalog')
StockRecord = get_model('partner', 'StockRecord')


@httpretty.activate
@ddt.ddt
class CatalogViewSetTest(CatalogMixin, DiscoveryMockMixin, ApiMockMixin, TestCase):
    """Test the Catalog and related products APIs."""

    catalog_list_path = reverse('api:v2:catalog-list')

    def setUp(self):
        super(CatalogViewSetTest, self).setUp()
        self.client.login(username=self.user.username, password=self.password)

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
        """The list endpoint should return only catalogs with current site's partner."""
        Catalog.objects.create(name='New catalog', partner=PartnerFactory())
        self.assertEqual(Catalog.objects.count(), 2)
        response = self.client.get(self.catalog_list_path)
        expected_data = self.serialize_catalog(self.catalog)
        response_data = response.json()
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
        self.assertDictEqual(response.json(), self.serialize_catalog(self.catalog))

    def test_catalog_products(self):
        """Verify the endpoint returns all products associated with a specific catalog."""
        path = reverse(
            'api:v2:catalog-product-list',
            kwargs={'parent_lookup_stockrecords__catalogs': self.catalog.id}
        )
        response = self.client.get(path)
        response_data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['count'], 0)
        self.assertListEqual(response_data['results'], [])

        self.catalog.stock_records.add(self.stock_record)

        response = self.client.get(path)
        response_data = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_data['count'], 1)

        expected_data = ProductSerializer(self.stock_record.product, context={'request': response.wsgi_request}).data
        self.assertListEqual(response_data['results'], [expected_data])

    def test_preview_success(self):
        """ Verify the endpoint returns a list of catalogs from the Catalog API. """
        self.mock_access_token_response()
        seat = self.course.create_or_update_seat('verified', False, 0)
        self.mock_course_runs_endpoint(self.site_configuration.discovery_api_url, course_run=self.course)

        url = '{path}?query=id:course*&seat_types=verified'.format(path=reverse('api:v2:catalog-preview'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()['seats'][0],
            ProductSerializer(seat, context={'request': response.wsgi_request}).data
        )

    @ddt.data(
        '',
        'foo=bar',
        'query=',
        'query=foo',
        'query=foo&seat_types=',
        'query=&seat_types=bar',
        'seat_types=bar',
    )
    def test_preview_with_invalid_parameters(self, querystring):
        """ Verify the endpoint returns HTTP 400 if the parameters are invalid. """
        url = '{path}?{qs}'.format(path=reverse('api:v2:catalog-preview'), qs=querystring)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    @ddt.data(ReqConnectionError, SlumberBaseException, Timeout)
    def test_preview_catalog_course_discovery_service_not_available(self, exc_class):
        """Test catalog query preview when course discovery is not available."""
        url = '{path}?query=foo&seat_types=bar'.format(path=reverse('api:v2:catalog-preview'))

        with mock.patch('ecommerce.coupons.utils.get_catalog_course_runs', side_effect=exc_class):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

    def test_course_catalogs_for_single_page_api_response(self):
        """
        Test course catalogs list view "course_catalogs" for valid response
        with catalogs in alphabetical order.
        """
        catalogs = ('Clean Catalog', 'ABC Catalog', 'New Catalog', 'Edx Catalog',)
        self.mock_access_token_response()
        self.mock_discovery_api(catalogs, self.site_configuration.discovery_api_url)

        response = self.client.get(reverse('api:v2:catalog-course-catalogs'))
        self.assertEqual(response.status_code, 200)

        actual = [catalog['name'] for catalog in response.data['results']]
        self.assertEqual(actual, sorted(catalogs))

    @mock.patch('ecommerce.extensions.api.v2.views.catalog.logger.exception')
    def test_get_course_catalogs_with_catalog_api_failure(self, mock_exception):
        """
        Verify that the course catalogs list view "course_catalogs" returns
        empty results list in case the Course Discovery API fails to return
        data.
        """
        self.mock_access_token_response()
        self.mock_discovery_api_failure(ReqConnectionError, self.site_configuration.discovery_api_url)

        response = self.client.get(reverse('api:v2:catalog-course-catalogs'))

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
        self.assertListEqual(response.json()['results'], [expected_data])

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
        self.assertDictEqual(response.json(), expected)
