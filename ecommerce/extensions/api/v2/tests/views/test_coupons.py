from __future__ import unicode_literals

import datetime
import json

from django.core.urlresolvers import reverse
from django.db.utils import IntegrityError
from django.test import RequestFactory
from oscar.core.loading import get_model

from ecommerce.core.models import Client
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.tests.factories import SiteFactory, SiteConfigurationFactory
from ecommerce.tests.mixins import CouponMixin
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Category = get_model('catalogue', 'Category')
Course = get_model('courses', 'Course')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')

COUPONS_LINK = reverse('api:v2:coupons-list')


class CouponViewSetTest(CouponMixin, TestCase):
    """Unit tests for creating coupon order."""

    def setUp(self):
        super(CouponViewSetTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        course_id = 'edx/Demo_Course/DemoX'
        course = Course.objects.create(id=course_id)
        course.create_or_update_seat('verified', True, 50, self.partner)

        self.catalog = Catalog.objects.create(partner=self.partner)
        self.product_class, __ = ProductClass.objects.get_or_create(name='Coupon')

    def test_create(self):
        """Test the create method."""
        site_configuration = SiteConfigurationFactory(partner__name='TestX')
        site = SiteFactory()
        site.siteconfiguration = site_configuration
        data = {
            'title': 'Test coupon',
            'client_username': 'Client',
            'stock_record_ids': [1],
            'start_date': '2015-1-1',
            'end_date': '2020-1-1',
            'code': '',
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'voucher_type': Voucher.SINGLE_USE,
            'quantity': 1,
            'price': 100,
            'category': 'Test category',
            'sub_category': ''
        }
        request = RequestFactory()
        request.data = data
        request.site = site

        response = CouponViewSet().create(request)

        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(
            response.data,
            {'payment_data': {'payment_processor_name': 'Invoice'}, 'id': 1, 'order': 1, 'coupon_id': 3}
        )

    def test_create_coupon_product(self):
        """Test the created coupon data."""
        coupon = self.create_coupon()
        self.assertEqual(Product.objects.filter(product_class=self.product_class).count(), 1)
        self.assertIsInstance(coupon, Product)
        self.assertEqual(coupon.title, 'Test coupon')

        self.assertEqual(StockRecord.objects.filter(product=coupon).count(), 1)
        stock_record = StockRecord.objects.get(product=coupon)
        self.assertEqual(stock_record.price_currency, 'USD')
        self.assertEqual(stock_record.price_excl_tax, 100)

        self.assertEqual(coupon.attr.coupon_vouchers.vouchers.count(), 5)
        category = ProductCategory.objects.get(product=coupon).category
        self.assertEqual(category.name, 'Test category')

    def test_append_to_existing_coupon(self):
        """Test adding additional vouchers to an existing coupon."""
        self.create_coupon(partner=self.partner, catalog=self.catalog)
        data = {
            'partner': self.partner,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'catalog': self.catalog,
            'end_date': datetime.date(2020, 1, 1),
            'code': '',
            'quantity': 2,
            'start_date': datetime.date(2015, 1, 1),
            'voucher_type': Voucher.MULTI_USE,
            'category': 'Test category',
            'sub_category': ''
        }
        coupon_append = CouponViewSet().create_coupon_product(
            title='Test coupon',
            price=100,
            data=data
        )

        self.assertEqual(Product.objects.filter(product_class=self.product_class).count(), 1)
        self.assertEqual(StockRecord.objects.filter(product=coupon_append).count(), 1)
        self.assertEqual(coupon_append.attr.coupon_vouchers.vouchers.count(), 7)
        self.assertEqual(coupon_append.attr.coupon_vouchers.vouchers.filter(usage=Voucher.MULTI_USE).count(), 2)

    def test_custom_code_string(self):
        """Test creating a coupon with custom voucher code."""
        data = {
            'partner': self.partner,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'catalog': self.catalog,
            'end_date': datetime.date(2020, 1, 1),
            'code': 'CUSTOMCODE',
            'quantity': 1,
            'start_date': datetime.date(2015, 1, 1),
            'voucher_type': Voucher.ONCE_PER_CUSTOMER,
            'category': 'Test category',
            'sub_category': ''
        }
        custom_coupon = CouponViewSet().create_coupon_product(
            title='Custom coupon',
            price=100,
            data=data
        )
        self.assertEqual(custom_coupon.attr.coupon_vouchers.vouchers.count(), 1)
        self.assertEqual(custom_coupon.attr.coupon_vouchers.vouchers.first().code, 'CUSTOMCODE')

    def test_custom_code_integrity_error(self):
        """Test custom coupon code duplication."""
        data = {
            'partner': self.partner,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'catalog': self.catalog,
            'end_date': datetime.date(2020, 1, 1),
            'code': 'CUSTOMCODE',
            'quantity': 1,
            'start_date': datetime.date(2015, 1, 1),
            'voucher_type': Voucher.SINGLE_USE,
            'category': 'Test category',
            'sub_category': ''
        }
        CouponViewSet().create_coupon_product(
            title='Custom coupon',
            price=100,
            data=data
        )

        with self.assertRaises(IntegrityError):
            CouponViewSet().create_coupon_product(
                title='Coupon with integrity issue',
                price=100,
                data=data
            )

    def test_add_product_to_basket(self):
        """Test adding a coupon product to a basket."""
        coupon = self.create_coupon(partner=self.partner)
        coupon_client = Client.objects.create(username='TestX')
        basket = CouponViewSet().add_product_to_basket(
            product=coupon,
            client=coupon_client,
            site=self.site,
            partner=self.partner
        )

        self.assertIsInstance(basket, Basket)
        self.assertEqual(Basket.objects.count(), 1)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.lines.first().price_excl_tax, 100)

    def test_create_order(self):
        """Test the order creation."""
        coupon = self.create_coupon(partner=self.partner)
        coupon_client = Client.objects.create(username='TestX')
        basket = CouponViewSet().add_product_to_basket(
            product=coupon,
            client=coupon_client,
            site=self.site,
            partner=self.partner
        )
        response_data = CouponViewSet().create_order_for_invoice(basket, coupon_id=coupon.id)
        self.assertEqual(response_data[AC.KEYS.BASKET_ID], 1)
        self.assertEqual(response_data[AC.KEYS.ORDER], 1)
        self.assertEqual(response_data[AC.KEYS.PAYMENT_DATA][AC.KEYS.PAYMENT_PROCESSOR_NAME], 'Invoice')

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.first().status, 'Complete')
        self.assertEqual(Order.objects.first().total_incl_tax, 100)
        self.assertEqual(Basket.objects.first().status, 'Submitted')


class CouponViewSetFunctionalTest(CouponMixin, TestCase):
    """Test the coupon order creation functionality."""

    def setUp(self):
        super(CouponViewSetFunctionalTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        course_id = 'edx/Demo_Course/DemoX'
        course = Course.objects.create(id=course_id)
        course.create_or_update_seat('verified', True, 50, self.partner)

        course_id = 'edx/Demo_Course2/DemoX'
        course = Course.objects.create(id=course_id)
        course.create_or_update_seat('verified', True, 100, self.partner)
        self.data = {
            'title': 'Test coupon',
            'client_username': 'TestX',
            'stock_record_ids': [1, 2],
            'start_date': '2015-01-01',
            'end_date': '2020-01-01',
            'code': '',
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'voucher_type': Voucher.SINGLE_USE,
            'quantity': 2,
            'price': 100,
            'category': 'Test category',
            'sub_category': ''
        }
        self.response = self.client.post(COUPONS_LINK, data=self.data, format='json')

    def test_response(self):
        """Test the response data given after the order was created."""
        self.assertEqual(self.response.status_code, 200)
        response_data = json.loads(self.response.content)
        self.assertEqual(response_data[AC.KEYS.COUPON_ID], 5)
        self.assertEqual(response_data[AC.KEYS.BASKET_ID], 1)
        self.assertEqual(response_data[AC.KEYS.ORDER], 1)
        self.assertEqual(response_data[AC.KEYS.PAYMENT_DATA][AC.KEYS.PAYMENT_PROCESSOR_NAME], 'Invoice')

    def test_order(self):
        """Test the order data after order creation."""
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.first().status, 'Complete')
        self.assertEqual(Order.objects.first().lines.count(), 1)
        self.assertEqual(Order.objects.first().lines.first().product.title, 'Test coupon')

    def test_authentication_required(self):
        """Test that a guest cannot access the view."""
        response = self.client.post(COUPONS_LINK, data=self.data)
        self.assertEqual(response.status_code, 200)

        self.client.logout()
        response = self.client.post(COUPONS_LINK, data=self.data)
        self.assertEqual(response.status_code, 401)

    def test_authorization_required(self):
        """Test that a non-staff user cannot access the view."""
        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)

        response = self.client.post(COUPONS_LINK, data=self.data)
        self.assertEqual(response.status_code, 403)

    def test_list_coupons(self):
        """Test that the endpoint returns information needed for the details page."""
        response = self.client.get(COUPONS_LINK)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        coupon_data = response_data['results'][0]
        self.assertEqual(coupon_data['title'], 'Test coupon')
        self.assertEqual(coupon_data['coupon_type'], 'Enrollment code')
        self.assertIsNotNone(coupon_data['last_edited'][0])
        self.assertEqual(coupon_data['seats'][0]['attribute_values'][0]['value'], 'verified')
        self.assertEqual(coupon_data['seats'][0]['attribute_values'][1]['value'], 'edx/Demo_Course2/DemoX')
        self.assertEqual(coupon_data['vouchers'][0]['benefit'][1], 100.0)
        self.assertIsNotNone(coupon_data['vouchers'][0]['redeem_url'])
        self.assertEqual(coupon_data['vouchers'][0]['start_datetime'], '2015-01-01T05:00:00Z')
        self.assertEqual(coupon_data['vouchers'][0]['end_datetime'], '2020-01-01T05:00:00Z')
        self.assertIsNotNone(coupon_data['vouchers'][0]['code'])
        self.assertTrue(coupon_data['vouchers'][0]['is_available_to_user'][0])
        self.assertEqual(coupon_data['client'], 'TestX')
        self.assertEqual(coupon_data['price'], '100.00')

        self.data['title'] = 'Test discount code'
        self.data['benefit_value'] = 20
        self.client.post(COUPONS_LINK, data=self.data, format='json')
        response = self.client.get(COUPONS_LINK)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['results'][0]['coupon_type'], 'Discount code')
        self.assertEqual(response_data['results'][0]['vouchers'][0]['benefit'][1], 20.0)

    def test_update(self):
        """Test updating a coupon."""
        coupon = Product.objects.get(title='Test coupon')
        path = reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id})
        response = self.client.put(path, json.dumps({'title': 'New title'}), 'application/json')
        response_data = json.loads(response.content)
        self.assertEqual(response_data['id'], coupon.id)
        self.assertEqual(response_data['title'], 'New title')

    def test_update_datetimes(self):
        """Test that updating a coupons date updates all of it's voucher dates."""
        coupon = Product.objects.get(title='Test coupon')
        voucher_code = coupon.attr.coupon_vouchers.vouchers.first().code
        path = reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id})
        data = {
            'id': coupon.id,
            'start_datetime': '2030-01-01',
            'end_datetime': '2035-01-01'
        }
        response = self.client.put(path, json.dumps(data), 'application/json')
        response_data = json.loads(response.content)
        self.assertEqual(response_data['id'], coupon.id)
        self.assertEqual(response_data['title'], 'Test coupon')

        new_coupon = Product.objects.get(id=coupon.id)
        self.assertEqual(new_coupon.attr.coupon_vouchers.vouchers.first().code, voucher_code)
        self.assertEqual(new_coupon.attr.coupon_vouchers.vouchers.first().start_datetime.year, 2030)
        self.assertEqual(new_coupon.attr.coupon_vouchers.vouchers.last().start_datetime.year, 2030)
        self.assertEqual(new_coupon.attr.coupon_vouchers.vouchers.first().end_datetime.year, 2035)
        self.assertEqual(new_coupon.attr.coupon_vouchers.vouchers.last().end_datetime.year, 2035)
