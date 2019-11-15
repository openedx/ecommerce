# encoding: utf-8
"""
Contains the tests for creating an coupon associated with enterprise customer and catalog.
"""

from __future__ import absolute_import, unicode_literals

from uuid import uuid4

from django.core.management import call_command
from django.utils.timezone import now
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
        'SOCIAL_AUTH_EDX_OIDC_URL_ROOT': 'http://edx.devstack.lms:18000/oauth2',
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
        CategoryFactory.create(slug='coupons')
        self.ent_customer_uuid = str(uuid4())

    @patch('ecommerce.enterprise.management.commands.seed_enterprise_devstack_data.EdxRestApiClient.get_oauth_access_token')
    def test_get_access_token(self, mock_api_client):
        """ TODO """
        # sanity check that SiteConfiguration has the correct oauth_settings
        assert self.command.site.oauth_settings == self.site_oauth_settings

        self.command._get_access_token()
        oauth_settings = self.command.site.oauth_settings
        mock_api_client.assert_called_with(
            '{}/access_token/'.format(oauth_settings.get('SOCIAL_AUTH_EDX_OIDC_URL_ROOT')),
            oauth_settings.get('BACKEND_SERVICE_EDX_OAUTH2_KEY'),
            oauth_settings.get('BACKEND_SERVICE_EDX_OAUTH2_SECRET'),
            token_type='jwt',
        )

    @patch.object(seed_command, '_get_access_token')
    def test_get_headers(self, mock_get_access_token):
        """ TODO """
        access_token = 'fake_access_token'
        mock_get_access_token.return_value = (access_token, now())
        headers = self.command._get_headers()
        assert headers == {'Authorization': 'JWT {}'.format(access_token)}

    @patch('requests.get')
    def test_get_enterprise_customer(self, mock_request):
        """ TODO """
        url = '{}enterprise-customer/'.format(self.command.site.enterprise_api_url)
        self.command._get_enterprise_customer(url=url)
        mock_request.assert_called_with(url, headers={}, params=None)
        self.command._get_enterprise_customer(
            url=url,
            enterprise_customer_uuid=self.ent_customer_uuid
        )
        mock_request.assert_called_with(
            url,
            headers={},
            params={'uuid': self.ent_customer_uuid},
        )

    @patch('requests.get')
    def test_get_enterprise_catalog(self, mock_request):
        """ TODO """
        url = '{}enterprise_catalogs/'.format(self.command.site.enterprise_api_url)
        self.command.enterprise_customer = {'uuid': self.ent_customer_uuid}
        self.command._get_enterprise_catalog(url=url)
        mock_request.assert_called_with(
            url,
            headers={},
            params={'enterprise_customer': self.ent_customer_uuid},
        )

    @patch('requests.post')
    def test_create_coupon(self, mock_request):
        """ TODO """
        catalog_uuid = str(uuid4())
        ecommerce_api_url = self.command.site.build_ecommerce_url() + '/api/v2'
        self.command.enterprise_customer = {'uuid': self.ent_customer_uuid}
        self.command.enterprise_catalog = {'uuid': catalog_uuid}
        self.command._create_coupon(ecommerce_api_url)

    @patch('requests.post')
    @patch.object(seed_command, '_get_enterprise_catalog')
    @patch.object(seed_command, '_get_enterprise_customer')
    @patch.object(seed_command, '_get_access_token')
    def test_ent_coupon_creation(self, mock_access_token, mock_ent_customer, mock_ent_catalog, mock_coupon_post):
        """
        Verify a coupon is created for an enterprise customer/catalog
        """
        mock_coupon_post_res = {'data': 'some data'}

        # create return values for mocked methods
        mock_access_token.return_value = ('fake_access_token', now())
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
                    'uuid': str(uuid4()),
                    'title': 'Test Enterprise Catalog',
                    'enterprise_customer': self.ent_customer_uuid,
                }
            ]
        }
        mock_coupon_post.return_value = Mock(
            status_code=200,
            json=lambda: mock_coupon_post_res,
        )
        with patch(self.logger) as patched_log:
            call_command('seed_enterprise_devstack_data')
            patched_log.info.assert_called_with('\nEnterprise coupon successfully created: %s', mock_coupon_post_res)
