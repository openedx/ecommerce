from django.core.management import call_command
from oscar.core.loading import get_model
from oscar.test.factories import OrderFactory

from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.extensions.order.management.commands.migrate_partner_to_orders'
Order = get_model('order', 'Order')


class MigratePartnerToOrdersTests(TestCase):

    def test_migrate_partner(self):
        """ Test that command successfully add partner to orders."""
        initial_count = 4
        SiteConfigurationFactory()
        OrderFactory.create_batch(initial_count, partner=None)
        self.assertEqual(Order.objects.filter(partner__isnull=True).count(), initial_count)

        call_command(
            'migrate_partner_to_orders', batch_size=2, sleep_time=1
        )

        self.assertEqual(Order.objects.filter(partner__isnull=True).count(), 0)
