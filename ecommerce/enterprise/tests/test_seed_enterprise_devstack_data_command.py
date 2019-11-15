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

from ecommerce.enterprise.management.commands.seed_enterprise_devstack_data import Command as seed_command
from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.testcases import TransactionTestCase

SiteConfiguration = get_model('core', 'SiteConfiguration')


class SeedEnterpriseDevstackDataTests(TransactionTestCase):
    """
    Tests the seed enterprise devstack data management command.
    """
    logger = 'ecommerce.enterprise.management.commands.seed_enterprise_devstack_data.logger'

    def setUp(self):
        """
        Set up initial data (e.g., site configuration) prior to running tests
        """
        super(SeedEnterpriseDevstackDataTests, self).setUp()
        SiteConfigurationFactory.create()
        self.ent_customer_uuid = str(uuid4())

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
