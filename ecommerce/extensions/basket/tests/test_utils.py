from django.test import RequestFactory
from oscar.core.loading import get_model
from oscar.test.factories import ProductFactory, VoucherFactory

from ecommerce.extensions.basket.utils import get_product_from_sku, prepare_basket
from ecommerce.tests.factories import PartnerFactory, SiteConfigurationFactory, StockRecordFactory
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')


class BasketUtilsTests(TestCase):
    """ Tests for basket utility functions. """
    def setUp(self):
        super(BasketUtilsTests, self).setUp()
        self.user = self.create_user()

    def test_prepare_basket(self):
        """ Verify a basket is returned. """
        request = RequestFactory()
        product = ProductFactory()
        voucher = VoucherFactory()
        site_configuration = SiteConfigurationFactory(partner__name='Tester')
        request.site = site_configuration.site

        basket = prepare_basket(request, self.user, product, voucher)
        self.assertIsNotNone(basket)

        basket_no_voucher = prepare_basket(request, self.user, product)
        self.assertFalse(basket_no_voucher.vouchers.all())

    def test_get_product_from_sku(self):
        """ Verify get_product_from_sku() returns product if correct information is provided. """
        partner = PartnerFactory(name='Test')
        sku = 'TEST123'
        StockRecordFactory(partner=partner, partner_sku=sku)

        sr, __ = get_product_from_sku(partner, sku)
        self.assertIsNotNone(sr)

        sr_none, msg = get_product_from_sku(partner, sku='NONE')
        self.assertIsNone(sr_none)
        self.assertEqual(msg, 'SKU [NONE] does not exist for partner [Test].')
