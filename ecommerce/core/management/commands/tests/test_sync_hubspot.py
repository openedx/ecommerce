"""
Test the sync_hubspot management command
"""
from django.core.management import call_command
from django.test import TestCase
from django.utils.six import StringIO
from factory.django import get_model
from mock import patch

from ecommerce.core.management.commands.sync_hubspot import Command as sync_command
from ecommerce.tests.factories import SiteConfigurationFactory

SiteConfiguration = get_model('core', 'SiteConfiguration')


class TestSyncHubspotCommand(TestCase):
    """
    Test sync_hubspot management command.
    """

    def setUp(self):
        super(TestSyncHubspotCommand, self).setUp()
        self.site_config = SiteConfigurationFactory()
        self.hubspot_site_config = SiteConfigurationFactory.create(
            hubspot_secret_key='test_key',
        )

    def test_with_no_hubspot_secret_keys(self):
        """Test with SiteConfiguration having NOT any hubspot_secret_key"""
        # removing keys
        SiteConfiguration.objects.update(hubspot_secret_key=None)

        # making sure there are still SiteConfigurations exists
        self.assertTrue(SiteConfiguration.objects.count() > 0)

        out = StringIO()
        call_command('sync_hubspot', stdout=out)
        output = out.getvalue()
        self.assertIn('No Hubspot enabled SiteConfiguration Found.', output)

    def test_with_hubspot_secret_key(self):
        """Test with SiteConfiguration having hubspot_secret_key"""
        with patch.object(sync_command, '_install_hubspot_ecommerce_bridge') as mock_install, \
                patch.object(sync_command, '_define_hubspot_ecommerce_settings') as mock_settings:
            out = StringIO()
            call_command('sync_hubspot', stdout=out)
            output = out.getvalue()
            self.assertIn('Started syncing data', output)
            self.assertEqual(mock_install.call_count, 1)
            self.assertEqual(mock_settings.call_count, 1)
