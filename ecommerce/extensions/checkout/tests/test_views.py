from decimal import Decimal

from django.core.urlresolvers import reverse
from django.conf import settings
import httpretty
from oscar.core.loading import get_model
from oscar.test import newfactories as factories

from ecommerce.core.url_utils import get_lms_url
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')


class FreeCheckoutViewTests(TestCase):
    """ FreeCheckoutView view tests. """
    path = reverse('checkout:free-checkout')

    def setUp(self):
        super(FreeCheckoutViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def prepare_basket(self, price):
        """ Helper function that creates a basket and adds a product with set price to it. """
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(factories.ProductFactory(stockrecords__price_excl_tax=price), 1)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.total_incl_tax, Decimal(price))

    def test_empty_basket(self):
        """ Verify redirect to basket summary in case of empty basket. """
        response = self.client.get(self.path)
        expected_url = self.get_full_url(reverse('basket:summary'))
        self.assertRedirects(response, expected_url)

    def test_non_free_basket(self):
        """ Verify an exception is raised when the URL is being accessed to with a non-free basket. """
        self.prepare_basket(10)

        with self.assertRaises(BasketNotFreeError):
            self.client.get(self.path)

    @httpretty.activate
    def test_successful_redirect(self):
        """ Verify redirect to the receipt page. """
        self.prepare_basket(0)
        self.assertEqual(Order.objects.count(), 0)
        receipt_page = get_lms_url(settings.RECEIPT_PAGE_PATH)

        response = self.client.get(self.path)
        self.assertEqual(Order.objects.count(), 1)

        expected_url = '{}?orderNum={}'.format(receipt_page, Order.objects.first().number)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)


class CancelResponseViewTests(TestCase):
    """ Tests for the CancelResponseView view. """

    def setUp(self):
        super(CancelResponseViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        self.basket = factories.BasketFactory(owner=self.user, site=self.site)
        product = factories.ProductFactory()
        voucher = factories.VoucherFactory()

        self.basket.add_product(product, 1)
        self.basket.vouchers.add(voucher)
        self.path = reverse('checkout:cancel', kwargs={'basket_id': self.basket.id})

    def test_cancel_response_redirect(self):
        """ Verify the frozen basket is thawed. """
        self.basket.freeze()
        basket_url = self.get_full_url(reverse('basket:summary'))
        response = self.client.get(self.path)
        self.assertRedirects(response, basket_url, fetch_redirect_response=False)

        basket = Basket.get_basket(self.user, self.site)
        self.assertEqual(basket, self.basket)
        self.assertEqual(basket.status, Basket.OPEN)

    def test_no_basket(self):
        """ Verify an error is returned for non-existing basket. """
        self.basket.delete()
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 404)
