from django.test import RequestFactory
from oscar.core.loading import get_model
from oscar.test.factories import ProductFactory, VoucherFactory

from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')


class BasketUtilsTests(TestCase):
    """ Tests for basket utility functions. """

    def setUp(self):
        super(BasketUtilsTests, self).setUp()
        self.request = RequestFactory()
        self.request.user = self.create_user()
        site_configuration = SiteConfigurationFactory(partner__name='Tester')
        self.request.site = site_configuration.site
        self.product = ProductFactory()

    def _prepare_basket(self, voucher=None):
        """ Create a basket with prepare_basket() and verify that the product is added. """
        basket = prepare_basket(self.request, self.product, voucher)
        self.assertIsNotNone(basket)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.lines.first().product, self.product)
        return basket

    def test_prepare_basket_with_voucher(self):
        """ Verify a basket is returned and contains a voucher. """
        voucher = VoucherFactory()
        basket = self._prepare_basket(voucher)
        self.assertEqual(basket.vouchers.count(), 1)

    def test_prepare_basket_without_voucher(self):
        """ Verify a basket is returned and does not contain a voucher. """
        basket_no_voucher = self._prepare_basket()
        self.assertFalse(basket_no_voucher.vouchers.all())
