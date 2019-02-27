"""
Test the sync_hubspot management command
"""
from datetime import datetime, timedelta
from StringIO import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from factory.django import get_model
from mock import patch
from oscar.test.factories import UserFactory
from slumber.exceptions import HttpClientError

from ecommerce.core.management.commands.sync_hubspot import Command as sync_command
from ecommerce.extensions.test.factories import create_order
from ecommerce.tests.factories import SiteConfigurationFactory

SiteConfiguration = get_model('core', 'SiteConfiguration')


class TestSyncHubspotCommand(TestCase):
    """
    Test sync_hubspot management command.
    """
    order = None
    hubspot_site_configuration = None

    def setUp(self):
        super(TestSyncHubspotCommand, self).setUp()
        self.hubspot_site_configuration = SiteConfigurationFactory.create(
            hubspot_secret_key='test_key',
        )
        self.order = self._create_order('1122', self.hubspot_site_configuration.site)

    def _create_order(self, order_number, site):
        """
        Creates the order with given order_number and
        site also update the order's product's title.
        """
        order = create_order(
            number="order-{order_number}".format(order_number=order_number),
            site=site,
            user=UserFactory()
        )
        order_line = order.lines.first()
        product = order_line.product
        product.title = "product-title-{order_number}".format(order_number=order_number)
        product.save()
        return order

    def _mocked_recent_modified_deal_endpoint(self):
        """
        Returns mocked recent_modified_deal_endpoint's response
        """
        return {'results': [{'properties': {'ip__ecomm_bridge__order_number': {'value': self.order.number}}}]}

    def _mocked_sync_errors_messages_endpoint(self):
        """
        Returns mocked sync_errors_messages_endpoint's response
        """
        return {'results': [
            {'objectType': 'DEAL', 'integratorObjectId': '1234', 'details': 'dummy-details-deal'},
            {'objectType': 'PRODUCT', 'integratorObjectId': '4321', 'details': 'dummy-details-product'},
        ]}

    def _get_command_output(self, is_stderr=False, initial_sync_days=7):
        """
        Runs the command and returns the stdout or stderr output of command.
        """
        out = StringIO()
        initial_sync_days_param = '--initial-sync-day=' + str(initial_sync_days)
        if is_stderr:
            call_command('sync_hubspot', initial_sync_days_param, stderr=out)
        else:
            call_command('sync_hubspot', initial_sync_days_param, stdout=out)
        return out.getvalue()

    @patch.object(sync_command, '_hubspot_endpoint')
    def test_with_no_hubspot_secret_keys(self, mocked_hubspot):
        """
        Test with SiteConfiguration having NOT any hubspot_secret_key.
        """
        # removing keys
        SiteConfiguration.objects.update(hubspot_secret_key='')

        # making sure there are still SiteConfigurations exists
        self.assertTrue(SiteConfiguration.objects.count() > 0)
        output = self._get_command_output()
        self.assertIn('No Hubspot enabled SiteConfiguration Found.', output)
        self.assertEqual(mocked_hubspot.call_count, 0)

    @patch.object(sync_command, '_hubspot_endpoint')
    def test_without_last_synced_order(self, mocked_hubspot):
        """
        Test with SiteConfiguration having hubspot_secret_key and last_synced_order doesn't exit.
        1. Install Bridge
        2. Define settings
        3. Upsert(PRODUCT)
        4. Upsert(CONTACT)
        5. Upsert(DEAL)
        6. Upsert(LINE ITEM)
        7. Sync-error
        """
        initial_sync_days = 4
        with patch.object(sync_command, '_get_last_synced_order', return_value=''):
            output = self._get_command_output(initial_sync_days=initial_sync_days)
            self.assertIn('No last synced order found. Pulled unsynced orders for site {site} from {start_date}'.format(
                site=self.hubspot_site_configuration.site.domain,
                start_date=datetime.now().date() - timedelta(initial_sync_days)
            ), output)
            self.assertEqual(mocked_hubspot.call_count, 7)

    @patch.object(sync_command, '_hubspot_endpoint')
    def test_with_last_synced_order(self, mocked_hubspot):
        """
        Test with SiteConfiguration having hubspot_secret_key and there exists a last sync order.
        1. Install Bridge
        2. Define settings
        3. Upsert(PRODUCT)
        4. Upsert(CONTACT)
        5. Upsert(DEAL)
        6. Upsert(LINE ITEM)
        7. Sync-error
        """
        with patch.object(sync_command, '_get_last_synced_order', return_value=self.order):
            self._create_order('11221', self.hubspot_site_configuration.site)
            output = self._get_command_output()
            self.assertIn('Pulled unsynced orders', output)
            self.assertEqual(mocked_hubspot.call_count, 7)

    @patch.object(sync_command, '_hubspot_endpoint')
    def test_last_synced_order(self, mocked_hubspot):
        """
        Test when _get_last_synced_order function raises an exception.
        1. Recent Modified Deal.
        2. Sync Error.
        """
        with patch.object(sync_command, '_install_hubspot_ecommerce_bridge', return_value=True), \
                patch.object(sync_command, '_define_hubspot_ecommerce_settings', return_value=True):
            # mocked the Recent Modified Deal endpoint
            mocked_hubspot.return_value = self._mocked_recent_modified_deal_endpoint()
            output = self._get_command_output()
            self.assertIn('No data found to sync', output)
            self.assertEqual(mocked_hubspot.call_count, 2)

            mocked_hubspot.return_value = {'results': [{'dummy': 'dummy'}]}
            output = self._get_command_output(is_stderr=True)
            self.assertIn('An error occurred while getting the last sync order', output)

            with self.assertRaises(CommandError):
                # if Recent Modified Deal raises an exception
                mocked_hubspot.side_effect = HttpClientError
                output = self._get_command_output()
                # command will stop when _get_last_synced_order doesn't work properly
                self.assertEqual('', output)

    @patch.object(sync_command, '_hubspot_endpoint')
    def test_upsert_hubspot_objects(self, mocked_hubspot):
        """
        Test when _upsert_hubspot_objects function raises an exception.
        """
        with patch.object(sync_command, '_install_hubspot_ecommerce_bridge', return_value=True), \
                patch.object(sync_command, '_define_hubspot_ecommerce_settings', return_value=True), \
                patch.object(sync_command, '_get_last_synced_order', return_value=''):
            # if _upsert_hubspot_objects raises an exception
            mocked_hubspot.side_effect = HttpClientError
            output = self._get_command_output(is_stderr=True)
            self.assertIn('An error occurred while upserting', output)

    @patch.object(sync_command, '_hubspot_endpoint')
    def test_install_hubspot_ecommerce_bridge(self, mocked_hubspot):
        """
        Test _install_hubspot_ecommerce_bridge function.
        """
        with patch.object(sync_command, '_get_last_synced_order', return_value=self.order):
            output = self._get_command_output()
            self.assertIn('Successfully installed hubspot ecommerce bridge', output)
            # if _install_hubspot_ecommerce_bridge raises an exception
            mocked_hubspot.side_effect = HttpClientError
            output = self._get_command_output(is_stderr=True)
            self.assertIn('An error occurred while installing hubspot ecommerce bridge', output)

    @patch.object(sync_command, '_hubspot_endpoint')
    def test_define_hubspot_ecommerce_settings(self, mocked_hubspot):
        """
        Test _define_hubspot_ecommerce_settings function.
        """
        with patch.object(sync_command, '_install_hubspot_ecommerce_bridge', return_value=True), \
                patch.object(sync_command, '_get_last_synced_order', return_value=self.order):
            output = self._get_command_output()
            self.assertIn('Successfully defined the hubspot ecommerce settings', output)
            # if _define_hubspot_ecommerce_settings raises an exception
            mocked_hubspot.side_effect = HttpClientError
            output = self._get_command_output(is_stderr=True)
            self.assertIn('An error occurred while defining hubspot ecommerce settings', output)

    @patch.object(sync_command, '_hubspot_endpoint')
    def test_sync_errors_messages_endpoint(self, mocked_hubspot):
        """
        Test _call_sync_errors_messages_endpoint function.
        """
        with patch.object(sync_command, '_install_hubspot_ecommerce_bridge', return_value=True), \
                patch.object(sync_command, '_define_hubspot_ecommerce_settings', return_value=True), \
                patch.object(sync_command, '_sync_data'):
            mocked_response = self._mocked_sync_errors_messages_endpoint()
            mocked_hubspot.return_value = mocked_response
            output = self._get_command_output()
            self.assertIn(
                'sync-error endpoint: for {object_type} with id {id} for site {site}: {message}'.format(
                    object_type=mocked_response.get('results')[0].get('objectType'),
                    id=mocked_response.get('results')[0].get('integratorObjectId'),
                    site=self.hubspot_site_configuration.site.domain,
                    message=mocked_response.get('results')[0].get('details')
                ),
                output
            )
            # if _call_sync_errors_messages_endpoint raises an exception
            mocked_hubspot.side_effect = HttpClientError
            output = self._get_command_output(is_stderr=True)
            self.assertIn(
                'An error occurred while getting the error syncing message',
                output
            )

    def test_hubspot_endpoint(self):
        """
        Test _hubspot_endpoint function.
        1. Install Bridge
        2. Define settings
        3. Upsert(PRODUCT)
        4. Upsert(CONTACT)
        5. Upsert(DEAL)
        6. Upsert(LINE ITEM)
        7. Sync-error
        """
        with patch('ecommerce.core.management.commands.sync_hubspot.EdxRestApiClient') as mock_client, \
                patch.object(sync_command, '_get_last_synced_order', return_value=None):
            output = self._get_command_output()
            self.assertEqual(mock_client.call_count, 7)
            self.assertIn('Successfully installed hubspot ecommerce bridge', output)
            self.assertIn('Successfully defined the hubspot ecommerce settings', output)
