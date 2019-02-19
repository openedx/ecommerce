"""
Test the sync_hubspot management command
"""
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils.six import StringIO
from factory.django import get_model
from mock import patch
from slumber.exceptions import HttpClientError

from ecommerce.core.management.commands.sync_hubspot import Command as sync_command
from ecommerce.extensions.test.factories import create_order
from ecommerce.tests.factories import SiteConfigurationFactory

SiteConfiguration = get_model('core', 'SiteConfiguration')


@patch.object(sync_command, '_hubspot_endpoint')
class TestSyncHubspotCommand(TestCase):
    """
    Test sync_hubspot management command.
    """

    def setUp(self):
        super(TestSyncHubspotCommand, self).setUp()
        self.hubspot_site_config = SiteConfigurationFactory.create(
            hubspot_secret_key='test_key',
        )
        self.product = None
        self.order_line = None
        self.order = self._create_order('1122', self.hubspot_site_config.site, set_up_call=True)

    def _create_order(self, order_number, site, set_up_call=False):
        """
        Creates the order with given order_number and site
        also update the order's product's title.
        """
        order = create_order(number="order-{order_number}".format(order_number=order_number), site=site)
        order_line = order.lines.first()
        product = order_line.product
        product.title = "product-title-{order_number}".format(order_number=order_number)
        product.save()
        if set_up_call:
            self.product = product
            self.order_line = order_line
        return order

    def _mocked_recent_modified_deal_response(self):
        return {'results': [{'properties': {'ip__ecomm_bridge__order_number': {'value': self.order.number}}}]}

    def _get_command_output(self):
        """
        Returns the stdout output of command.
        """
        out = StringIO()
        call_command('sync_hubspot', stdout=out)
        return out.getvalue()

    def test_with_no_hubspot_secret_keys(self, mocked_hubspot):
        """
        Test with SiteConfiguration having NOT any hubspot_secret_key
        """
        # removing keys
        SiteConfiguration.objects.update(hubspot_secret_key=None)

        # making sure there are still SiteConfigurations exists
        self.assertTrue(SiteConfiguration.objects.count() > 0)
        output = self._get_command_output()
        self.assertIn('No Hubspot enabled SiteConfiguration Found.', output)
        self.assertEqual(mocked_hubspot.call_count, 0)

    def test_first_sync_call(self, mocked_hubspot):
        """
        Test with SiteConfiguration having hubspot_secret_key and it is first hubspot sync call.
        1. Install Bridge
        2. Define settings
        3. Upsert(PRODUCT)
        4. Upsert(DEAL)
        5. Upsert(LINE ITEM)
        6. Sync-error
        """
        with patch.object(sync_command, '_get_last_synced_order', return_value=''):
            output = self._get_command_output()
            self.assertIn('It is first syncing call', output)
            self.assertEqual(mocked_hubspot.call_count, 6)

    def test_with_last_synced_order(self, mocked_hubspot):
        """
        Test with SiteConfiguration having hubspot_secret_key and there exists a last sync order.
        1. Install Bridge
        2. Define settings
        3. Upsert(PRODUCT)
        4. Upsert(DEAL)
        5. Upsert(LINE ITEM)
        6. Sync-error
        """
        with patch.object(sync_command, '_get_last_synced_order', return_value=self.order):
            self._create_order('11221', self.hubspot_site_config.site)
            output = self._get_command_output()
            self.assertIn('Pulled unsynced orders', output)
            self.assertEqual(mocked_hubspot.call_count, 6)

    # def test_no_data_to_sync(self, mocked_hubspot):
    #     """
    #     Test when there is no data to sync
    #     1. Install Bridge
    #     2. Define settings
    #     3. Sync-error
    #     """
    #     with patch.object(sync_command, '_get_last_synced_order', return_value=self.order):
    #         output = self._get_command_output()
    #         self.assertIn('No data found to sync', output)
    #         self.assertEqual(mocked_hubspot.call_count, 3)

    def test_with_exception(self, mocked_hubspot):
        """
        Test when _get_last_synced_order function raises an exception.
        1. Install Bridge
        2. Define settings
        """
        with patch.object(sync_command, '_get_last_synced_order', side_effect=CommandError):
            with self.assertRaises(CommandError):
                self._get_command_output()
                self.assertEqual(mocked_hubspot.call_count, 2)

    def test_last_synced_order(self, mocked_hubspot):
        """
        Test when _get_last_synced_order function raises an exception.
        1. Recent Modified Deal.
        2. Sync Error.
        """
        with patch.object(sync_command, '_install_hubspot_ecommerce_bridge', return_value=True):
            with patch.object(sync_command, '_define_hubspot_ecommerce_settings', return_value=True):
                # mocked the Recent Modified Deal endpoint
                mocked_hubspot.return_value = self._mocked_recent_modified_deal_response()
                output = self._get_command_output()
                self.assertIn('No data found to sync', output)
                self.assertEqual(mocked_hubspot.call_count, 2)

                # mocked the Recent Modified Deal with exception.
                mocked_hubspot.side_effect = HttpClientError
                self._get_command_output()
