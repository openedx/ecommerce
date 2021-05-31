import datetime
import urllib.error
import urllib.parse

import ddt
import mock
import pytz
from django.urls import reverse
from oscar.core.loading import get_class, get_model

from ecommerce.coupons.tests.mixins import DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.basket.constants import EMAIL_OPT_IN_ATTRIBUTE
from ecommerce.extensions.basket.tests.mixins import BasketMixin
from ecommerce.extensions.order.utils import UserAlreadyPlacedOrder
from ecommerce.extensions.test.factories import create_order
from ecommerce.tests.factories import ProductFactory, StockRecordFactory
from ecommerce.tests.mixins import LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Catalog = get_model('catalogue', 'Catalog')
Product = get_model('catalogue', 'Product')
OrderLine = get_model('order', 'Line')
Selector = get_class('partner.strategy', 'Selector')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


@ddt.ddt
class MobileBasketAddItemsViewTests(DiscoveryMockMixin, LmsApiMockMixin, BasketMixin,
                              EnterpriseServiceMockMixin, TestCase):
    """ MobileBasketAddItemsView view tests. """
    path = reverse('iap:mobile-basket-add')

    def setUp(self):
        super(MobileBasketAddItemsViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

        self.course = CourseFactory(partner=self.partner)
        product = self.course.create_or_update_seat('verified', False, 50)
        self.stock_record = StockRecordFactory(product=product, partner=self.partner)
        self.catalog = Catalog.objects.create(partner=self.partner)
        self.catalog.stock_records.add(self.stock_record)

    def _get_response(self, product_skus, **url_params):
        qs = urllib.parse.urlencode({'sku': product_skus}, True)
        url = '{root}?{qs}'.format(root=self.path, qs=qs)
        for name, value in url_params.items():
            url += '&{}={}'.format(name, value)
        return self.client.get(url)

    def test_add_multiple_products_to_basket(self):
        """ Verify the basket accepts multiple products. """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        response = self._get_response([product.stockrecords.first().partner_sku for product in products])
        self.assertEqual(response.status_code, 200)

        request = response.wsgi_request
        basket = Basket.get_basket(request.user, request.site)
        self.assertEqual(basket.status, Basket.OPEN)
        self.assertEqual(basket.lines.count(), len(products))

    def test_add_multiple_products_no_skus_provided(self):
        """ Verify the Bad request exception is thrown when no skus are provided. """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'No SKUs provided.')

    def test_add_multiple_products_no_available_products(self):
        """ Verify the Bad request exception is thrown when no skus are provided. """
        response = self.client.get(self.path, data=[('sku', 1), ('sku', 2)])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'Products with SKU(s) [1, 2] do not exist.')

    def test_all_already_purchased_products(self):
        """
        Test user can not purchase products again using the multiple item view
        """
        course = CourseFactory(partner=self.partner)
        product1 = course.create_or_update_seat("Verified", True, 0)
        product2 = course.create_or_update_seat("Professional", True, 0)
        stock_record = StockRecordFactory(product=product1, partner=self.partner)
        catalog = Catalog.objects.create(partner=self.partner)
        catalog.stock_records.add(stock_record)
        stock_record = StockRecordFactory(product=product2, partner=self.partner)
        catalog.stock_records.add(stock_record)

        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=True):
            response = self._get_response(
                [product.stockrecords.first().partner_sku for product in [product1, product2]],
            )
            self.assertEqual(response.status_code, 406)
            self.assertEqual(response.json()['error'], 'You have already purchased these products')

    def test_not_already_purchased_products(self):
        """
        Test user can purchase products which have not been already purchased
        """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        with mock.patch.object(UserAlreadyPlacedOrder, 'user_already_placed_order', return_value=False):
            response = self._get_response([product.stockrecords.first().partner_sku for product in products])
            self.assertEqual(response.status_code, 200)

    def test_one_already_purchased_product(self):
        """
        Test prepare_basket removes already purchased product and checkout for the rest of products
        """
        order = create_order(site=self.site, user=self.user)
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)
        products.append(OrderLine.objects.get(order=order).product)
        response = self._get_response([product.stockrecords.first().partner_sku for product in products])
        request = response.wsgi_request
        basket = Basket.get_basket(request.user, request.site)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(basket.lines.count(), len(products) - 1)

    def test_no_available_product(self):
        """ The view should return HTTP 400 if the product is not available for purchase. """
        product = self.stock_record.product
        product.expires = pytz.utc.localize(datetime.datetime.min)
        product.save()
        self.assertFalse(Selector().strategy().fetch_for_product(product).availability.is_available_to_buy)

        expected_content = 'No product is available to buy.'
        response = self._get_response(self.stock_record.partner_sku)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], expected_content)

    def test_with_both_unavailable_and_available_products(self):
        """ Verify the basket ignores unavailable products and continue with available products. """
        products = ProductFactory.create_batch(3, stockrecords__partner=self.partner)

        products[0].expires = pytz.utc.localize(datetime.datetime.min)
        products[0].save()
        self.assertFalse(Selector().strategy().fetch_for_product(products[0]).availability.is_available_to_buy)

        response = self._get_response([product.stockrecords.first().partner_sku for product in products])
        self.assertEqual(response.status_code, 200)

        request = response.wsgi_request
        basket = Basket.get_basket(request.user, request.site)
        self.assertEqual(basket.status, Basket.OPEN)

    @ddt.data(
        ('false', 'False'),
        ('true', 'True'),
    )
    @ddt.unpack
    def test_email_opt_in_when_explicitly_given(self, opt_in, expected_value):
        """
        Verify the email_opt_in query string is saved into a BasketAttribute.
        """
        response = self._get_response(self.stock_record.partner_sku, email_opt_in=opt_in)
        request = response.wsgi_request
        basket = Basket.get_basket(request.user, request.site)
        basket_attribute = BasketAttribute.objects.get(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE),
        )
        self.assertEqual(basket_attribute.value_text, expected_value)

    def test_email_opt_in_when_not_given(self):
        """
        Verify that email_opt_in defaults to false if not specified.
        """
        response = self._get_response(self.stock_record.partner_sku)
        request = response.wsgi_request
        basket = Basket.get_basket(request.user, request.site)
        basket_attribute = BasketAttribute.objects.get(
            basket=basket,
            attribute_type=BasketAttributeType.objects.get(name=EMAIL_OPT_IN_ATTRIBUTE),
        )
        self.assertEqual(basket_attribute.value_text, 'False')
