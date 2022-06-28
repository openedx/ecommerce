# encoding: utf-8
"""
Contains the tests for creating an coupon associated with enterprise customer and catalog.
"""
from uuid import uuid4

from django.core.management import call_command
from mock import Mock, patch
from oscar.core.loading import get_model
from oscar.test.factories import CategoryFactory

from ecommerce.enterprise.management.commands.seed_enterprise_devstack_data import Command as seed_command
from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.testcases import TransactionTestCase

SiteConfiguration = get_model('core', 'SiteConfiguration')


class SeedEnterpriseDevstackDataTests(TransactionTestCase):
    """
    Tests the seed enterprise devstack data management command.
    """
    logger = 'ecommerce.enterprise.management.commands.seed_enterprise_devstack_data.logger'
    site_oauth_settings = {
        'BACKEND_SERVICE_EDX_OAUTH2_PROVIDER_URL': 'http://edx.devstack.lms:18000/oauth2',
        'BACKEND_SERVICE_EDX_OAUTH2_KEY': 'ecommerce-backend-service-key',
        'BACKEND_SERVICE_EDX_OAUTH2_SECRET': 'ecommerce-backend-service-secret',
    }

    def setUp(self):
        """
        Set up initial data (e.g., site configuration, category) prior to running tests
        """
        super(SeedEnterpriseDevstackDataTests, self).setUp()
        self.site_config = SiteConfigurationFactory.create(
            oauth_settings=self.site_oauth_settings,
        )
        self.command = seed_command()
        self.command.site = self.site_config
        CategoryFactory.create(name='coupons')
        self.ent_customer_uuid = str(uuid4())
        self.ent_catalog_uuid = str(uuid4())
        self.access_token = 'fake_access_token'

    @patch('ecommerce.core.models.SiteConfiguration.oauth_api_client')
    def test_get_enterprise_customer(self, mock_api_client):
        """ Verify `get_enterprise_customer` returns the correct value """
        url = '{}enterprise-customer/'.format(self.command.site.enterprise_api_url)
        expected = {'uuid': self.ent_customer_uuid}
        mock_api_client.get.return_value = Mock(
            status_code=200,
            json=lambda: {'results': [expected]},
        )

        # NOT specifying an enterprise customer uuid
        result = self.command.get_enterprise_customer(mock_api_client, url=url)
        mock_api_client.get.assert_called_with(url, params=None)
        assert result == expected

        # specifying an enterprise customer uuid
        result = self.command.get_enterprise_customer(
            mock_api_client, url=url, enterprise_customer_uuid=self.ent_customer_uuid
        )
        mock_api_client.get.assert_called_with(
            url, params={'uuid': self.ent_customer_uuid},
        )
        assert result == expected

    @patch('ecommerce.core.models.SiteConfiguration.oauth_api_client')
    def test_get_enterprise_customer_index_error(self, mock_api_client):
        """
        Verify `get_enterprise_customer` returns the correct value and
        does not make a request
        """
        url = '{}enterprise-customer/'.format(self.command.site.enterprise_api_url)
        mock_api_client.get.return_value = Mock(
            status_code=200,
            json=lambda: {'results': []},
        )

        result = self.command.get_enterprise_customer(mock_api_client, url=url)
        mock_api_client.get.assert_called_with(url, params=None)
        assert result is None

    @patch('ecommerce.core.models.SiteConfiguration.oauth_api_client')
    def test_get_enterprise_catalog(self, mock_api_client):
        """ Verify `get_enterprise_catalog` returns the correct value """
        url = '{}enterprise_catalogs/'.format(self.command.site.enterprise_api_url)
        self.command.enterprise_customer = {'uuid': self.ent_customer_uuid}
        expected = {'uuid': self.ent_catalog_uuid}
        mock_api_client.get.return_value = Mock(
            status_code=200,
            json=lambda: {'results': [expected]},
        )
        result = self.command.get_enterprise_catalog(mock_api_client, url=url)
        mock_api_client.get.assert_called_with(
            url,
            params={'enterprise_customer': self.ent_customer_uuid},
        )
        assert result == expected

    @patch('ecommerce.core.models.SiteConfiguration.oauth_api_client')
    def test_get_enterprise_catalog_no_customer(self, mock_api_client):
        """
        Verify `get_enterprise_catalog` does not make a request when
        there is no enterprise customer
        """
        url = '{}enterprise_catalogs/'.format(self.command.site.enterprise_api_url)
        self.command.get_enterprise_catalog(mock_api_client, url=url)
        mock_api_client.get.assert_not_called()

    @patch('ecommerce.core.models.SiteConfiguration.oauth_api_client')
    def test_get_enterprise_catalog_index_error(self, mock_api_client):
        """
        Verify `get_enterprise_catalog` returns the correct value when
        there is no catalog returned
        """
        url = '{}enterprise_catalogs/'.format(self.command.site.enterprise_api_url)
        self.command.enterprise_customer = {'uuid': self.ent_customer_uuid}
        mock_api_client.get.return_value = Mock(
            status_code=200,
            json=lambda: {'results': []},
        )
        result = self.command.get_enterprise_catalog(mock_api_client, url=url)
        mock_api_client.get.assert_called_with(url, params={'enterprise_customer': self.ent_customer_uuid})
        assert result is None

    @patch('ecommerce.core.models.SiteConfiguration.oauth_api_client')
    def test_create_coupon(self, mock_api_client):
        """ Verify `create_coupon` returns the correct value """
        ecommerce_api_url = self.command.site.build_ecommerce_url() + '/api/v2'
        enterprise_catalog_api_url = self.command.site.enterprise_catalog_api_url + '/enterprise-catalogs'
        self.command.enterprise_customer = {'uuid': self.ent_customer_uuid}
        self.command.enterprise_catalog = {'uuid': self.ent_catalog_uuid}

        expected = {'data': 'some data'}
        mock_api_client.post.return_value = Mock(
            status_code=200,
            json=lambda: expected,
        )
        result = self.command.create_coupon(mock_api_client, ecommerce_api_url=ecommerce_api_url,
                                            enterprise_catalog_api_url=enterprise_catalog_api_url)
        mock_api_client.post.assert_called()
        assert result == expected

    @patch('ecommerce.core.models.SiteConfiguration.oauth_api_client')
    def test_create_coupon_no_customer(self, mock_api_client):
        """ Verify `create_coupon` returns the correct value """
        ecommerce_api_url = self.command.site.build_ecommerce_url() + '/api/v2'
        enterprise_catalog_api_url = self.command.site.enterprise_catalog_api_url + '/enterprise-catalogs'
        self.command.create_coupon(mock_api_client, ecommerce_api_url=ecommerce_api_url,
                                   enterprise_catalog_api_url=enterprise_catalog_api_url)
        mock_api_client.post.assert_not_called()

    @patch('ecommerce.core.models.SiteConfiguration.oauth_api_client')
    def test_create_coupon_no_catalog(self, mock_api_client):
        """ Verify `create_coupon` returns the correct value """
        ecommerce_api_url = self.command.site.build_ecommerce_url() + '/api/v2'
        enterprise_catalog_api_url = self.command.site.enterprise_catalog_api_url + '/enterprise-catalogs'
        self.command.enterprise_customer = {'uuid': self.ent_customer_uuid}
        self.command.create_coupon(mock_api_client, ecommerce_api_url=ecommerce_api_url,
                                   enterprise_catalog_api_url=enterprise_catalog_api_url)
        mock_api_client.post.assert_not_called()

    @patch.object(seed_command, 'get_enterprise_catalog')
    @patch.object(seed_command, 'get_enterprise_customer')
    @patch('ecommerce.core.models.SiteConfiguration.oauth_api_client')
    def test_handle(self, mock_api_client, mock_ent_customer, mock_ent_catalog):
        """
        Verify the entry point of the command without any args,
        and makes a POST request to create a coupon
        """
        expected = {'data': 'some data'}
        # create return values for mocked methods
        mock_ent_customer.return_value = {
            'results': [
                {
                    'uuid': self.ent_customer_uuid,
                    'name': 'Test Enterprise',
                    'slug': 'test-enterprise',
                }
            ]
        }
        mock_ent_catalog.return_value = {
            'results': [
                {
                    'uuid': self.ent_catalog_uuid,
                    'title': 'Test Enterprise Catalog',
                    'enterprise_customer': self.ent_customer_uuid,
                }
            ]
        }
        mock_api_client.post.return_value = Mock(
            status_code=200,
            json=lambda: expected,
        )
        call_command('seed_enterprise_devstack_data')
        mock_api_client.post.assert_called()

    @patch.object(seed_command, 'get_enterprise_catalog')
    @patch.object(seed_command, 'get_enterprise_customer')
    @patch('ecommerce.core.models.SiteConfiguration.oauth_api_client')
    def test_handle_no_customer(self, mock_api_client, mock_ent_customer, mock_ent_catalog):
        """
        Verify the entry point of the command without any args,
        makes a POST request to create a coupon, but returns
        no enterprise customer
        """
        # create return values for mocked methods
        mock_ent_customer.return_value = None
        call_command('seed_enterprise_devstack_data')
        mock_ent_catalog.assert_not_called()
        mock_api_client.post.assert_not_called()

    @patch.object(seed_command, 'get_enterprise_catalog')
    @patch.object(seed_command, 'get_enterprise_customer')
    @patch('ecommerce.core.models.SiteConfiguration.oauth_api_client')
    def test_handle_no_catalog(self, mock_api_client, mock_ent_customer, mock_ent_catalog):
        """
        Verify the entry point of the command without any args,
        makes a POST request to create a coupon, but returns
        no enterprise catalog
        """
        # create return values for mocked methods
        mock_ent_customer.return_value = {
            'results': [
                {
                    'uuid': self.ent_customer_uuid,
                    'name': 'Test Enterprise',
                    'slug': 'test-enterprise',
                }
            ]
        }
        mock_ent_catalog.return_value = None
        call_command('seed_enterprise_devstack_data')
        mock_api_client.post.assert_not_called()

    @patch.object(seed_command, 'get_enterprise_catalog')
    @patch.object(seed_command, 'get_enterprise_customer')
    @patch('ecommerce.core.models.SiteConfiguration.oauth_api_client')
    def test_handle_ent_customer_arg(self, mock_api_client, mock_ent_customer, mock_ent_catalog):
        """
        Verify the entry point of the command uses the `--enterprise-customer` arg,
        and makes a POST request to create a coupon
        """
        expected = {'data': 'some data'}
        # create return values for mocked methods
        mock_ent_customer.return_value = {
            'results': [
                {
                    'uuid': self.ent_customer_uuid,
                    'name': 'Test Enterprise',
                    'slug': 'test-enterprise',
                }
            ]
        }
        mock_ent_catalog.return_value = {
            'results': [
                {
                    'uuid': self.ent_catalog_uuid,
                    'title': 'Test Enterprise Catalog',
                    'enterprise_customer': self.ent_customer_uuid,
                }
            ]
        }
        mock_api_client.post.return_value = Mock(
            status_code=200,
            json=lambda: expected,
        )
        call_command('seed_enterprise_devstack_data', '--enterprise-customer={}'.format(self.ent_customer_uuid))
        url = '{}enterprise-customer/'.format(self.command.site.enterprise_api_url)
        mock_ent_customer.assert_called_with(
            mock_api_client,
            enterprise_customer_uuid=self.ent_customer_uuid,
            url=url,
        )
        mock_api_client.post.assert_called()
