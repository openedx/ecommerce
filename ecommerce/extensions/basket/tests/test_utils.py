import ddt

from django.test import RequestFactory
from oscar.core.loading import get_model
from oscar.test.factories import ProductFactory, RangeFactory

from ecommerce.extensions.basket.utils import get_certificate_type_display_value, prepare_basket
from ecommerce.extensions.partner.models import StockRecord
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.factories import SiteConfigurationFactory
from ecommerce.tests.testcases import TestCase

Benefit = get_model('offer', 'Benefit')
Basket = get_model('basket', 'Basket')


@ddt.ddt
class BasketUtilsTests(TestCase):
    """ Tests for basket utility functions. """

    def setUp(self):
        super(BasketUtilsTests, self).setUp()
        self.request = RequestFactory()
        self.request.user = self.create_user()
        site_configuration = SiteConfigurationFactory(partner__name='Tester')
        self.request.site = site_configuration.site

    def test_prepare_basket_with_voucher(self):
        """ Verify a basket is returned and contains a voucher and the voucher is applied. """
        # Prepare a product with price of 100 and a voucher with 10% discount for that product.
        product = ProductFactory(stockrecords__price_excl_tax=100)
        new_range = RangeFactory(products=[product, ])
        voucher, product = prepare_voucher(_range=new_range, benefit_value=10)

        stock_record = StockRecord.objects.get(product=product)
        self.assertEqual(stock_record.price_excl_tax, 100.00)

        basket = prepare_basket(self.request, product, voucher)
        self.assertIsNotNone(basket)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.lines.first().product, product)
        self.assertEqual(basket.vouchers.count(), 1)
        self.assertIsNotNone(basket.applied_offers())
        self.assertEqual(basket.total_discount, 10.00)
        self.assertEqual(basket.total_excl_tax, 90.00)

    def test_prepare_basket_without_voucher(self):
        """ Verify a basket is returned and does not contain a voucher. """
        product = ProductFactory()
        basket = prepare_basket(self.request, product)
        self.assertIsNotNone(basket)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.lines.first().product, product)
        self.assertFalse(basket.vouchers.all())
        self.assertFalse(basket.applied_offers())

    @ddt.data(
        ('honor', 'Honor'),
        ('verified', 'Verified'),
        ('professional', 'Professional'),
        ('audit', 'Audit')
    )
    @ddt.unpack
    def test_cert_display(self, cert_type, cert_display):
        """ Verify certificate display types. """
        self.assertEqual(get_certificate_type_display_value(cert_type), cert_display)

    def test_cert_display_assertion(self):
        """ Verify assertion for invalid cert type """
        self.assertRaises(ValueError, lambda: get_certificate_type_display_value('junk'))
