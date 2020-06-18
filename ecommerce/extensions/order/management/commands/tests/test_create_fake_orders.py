

from django.core.management import call_command
from django.core.management.base import CommandError
from oscar.core.loading import get_model
from oscar.test.factories import create_product, create_stockrecord
from testfixtures import LogCapture

from ecommerce.tests.factories import PartnerFactory, SiteConfigurationFactory
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.extensions.order.management.commands.create_fake_orders'
Order = get_model('order', 'Order')
Basket = get_model('basket', 'Basket')


class FakeOrdersTests(TestCase):

    def test_product_does_not_exist(self):
        with LogCapture(LOGGER_NAME) as log:
            with self.assertRaises(CommandError):
                call_command('create_fake_orders', '--count=5', '--sku=sku_11111')
                log.check(
                    (
                        LOGGER_NAME,
                        'EXCEPTION',
                        'No StockRecord for partner_sku sku_11111 exists.'
                    )
                )

    def test_site_does_not_exist(self):
        partner = PartnerFactory()
        product = create_product()
        stockrecord = create_stockrecord(product=product, partner_name=partner.name)
        with LogCapture(LOGGER_NAME) as log:
            with self.assertRaises(CommandError):
                call_command('create_fake_orders', '--count=5', '--sku={}'.format(stockrecord.partner_sku))
                log.check(
                    (
                        LOGGER_NAME,
                        'EXCEPTION',
                        'No default site exists for partner {}!'.format(partner.id)
                    )
                )

    def test_create_fake_orders(self):
        site_configuration = SiteConfigurationFactory()
        partner = site_configuration.partner
        partner.default_site = site_configuration.site
        partner.save()
        product = create_product()
        stockrecord = create_stockrecord(product=product, partner_name=partner.name)
        self.assertEqual(Order.objects.all().count(), 0)
        self.assertEqual(Basket.objects.all().count(), 0)
        call_command('create_fake_orders', '--count=5', '--sku={}'.format(stockrecord.partner_sku))
        self.assertEqual(Order.objects.all().count(), 5)
        self.assertEqual(Basket.objects.all().count(), 5)
