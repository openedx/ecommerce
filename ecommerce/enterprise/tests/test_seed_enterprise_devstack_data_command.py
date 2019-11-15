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
        CategoryFactory.create(name='coupons')
        self.ent_customer_uuid = str(uuid4())
        self.ent_catalog_uuid = str(uuid4())
        self.access_token = 'fake_access_token'

    @patch(
        'ecommerce.enterprise.management.commands.seed_enterprise_devstack_data'
        '.EdxRestApiClient.get_oauth_access_token'
    )
    def test_get_access_token(self, mock_api_client):
        """ Verify _get_access_token returns the correct value """
        # sanity check that SiteConfiguration has the correct oauth_settings
        assert self.command.site.oauth_settings == self.site_oauth_settings

        expected = (self.access_token, now())
        mock_api_client.return_value = expected
        result = self.command._get_access_token()
        oauth_settings = self.command.site.oauth_settings
        mock_api_client.assert_called_with(
            '{}/access_token/'.format(oauth_settings.get('SOCIAL_AUTH_EDX_OIDC_URL_ROOT')),
            oauth_settings.get('BACKEND_SERVICE_EDX_OAUTH2_KEY'),
            oauth_settings.get('BACKEND_SERVICE_EDX_OAUTH2_SECRET'),
            token_type='jwt',
        )
        assert expected == result

    @patch.object(seed_command, '_get_access_token')
    def test_get_headers(self, mock_get_access_token):
        """ Verify _get_headers returns the correct value """
        expected = {'Authorization': 'JWT {}'.format(self.access_token)}
        mock_get_access_token.return_value = (self.access_token, now())
        result = self.command._get_headers()
        assert expected == result

    @patch('requests.get')
    def test_get_enterprise_customer(self, mock_request):
        """ Verify _get_enterprise_customer returns the correct value """
        url = '{}enterprise-customer/'.format(self.command.site.enterprise_api_url)
        expected = {'uuid': self.ent_customer_uuid}
        mock_request.return_value = Mock(
            status_code=200,
            json=lambda: {'results': [expected]},
        )

        # NOT specifying an enterprise customer uuid
        result = self.command._get_enterprise_customer(url=url)
        mock_request.assert_called_with(url, headers={}, params=None)
        assert expected == result

        # specifying an enterprise customer uuid
        result = self.command._get_enterprise_customer(
            url=url, enterprise_customer_uuid=self.ent_customer_uuid
        )
        mock_request.assert_called_with(
            url, headers={}, params={'uuid': self.ent_customer_uuid},
        )
        assert expected == result

    @patch('requests.get')
    def test_get_enterprise_catalog(self, mock_request):
        """ Verify _get_enterprise_catalog returns the correct value """
        url = '{}enterprise_catalogs/'.format(self.command.site.enterprise_api_url)
        self.command.enterprise_customer = {'uuid': self.ent_customer_uuid}
        expected = {'uuid': self.ent_catalog_uuid}
        mock_request.return_value = Mock(
            status_code=200,
            json=lambda: {'results': [expected]},
        )
        result = self.command._get_enterprise_catalog(url=url)
        mock_request.assert_called_with(
            url,
            headers={},
            params={'enterprise_customer': self.ent_customer_uuid},
        )
        assert expected == result

    @patch('requests.post')
    def test_create_coupon(self, mock_request):
        """ Verify _create_coupon returns the correct value """
        ecommerce_api_url = self.command.site.build_ecommerce_url() + '/api/v2'
        self.command.enterprise_customer = {'uuid': self.ent_customer_uuid}
        self.command.enterprise_catalog = {'uuid': self.ent_catalog_uuid}

        expected = {'data': 'some data'}
        mock_request.return_value = Mock(
            status_code=200,
            json=lambda: expected,
        )
        result = self.command._create_coupon(ecommerce_api_url)
        mock_request.assert_called()
        assert expected == result
