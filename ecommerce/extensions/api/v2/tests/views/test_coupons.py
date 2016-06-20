# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import datetime
from decimal import Decimal

import ddt
import httpretty
import pytz
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db.utils import IntegrityError
from django.test import RequestFactory
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model
from oscar.test import factories
from rest_framework import status

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.coupons.tests.mixins import CatalogPreviewMockMixin, CouponMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.invoice.models import Invoice
from ecommerce.tests.factories import SiteConfigurationFactory, SiteFactory
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Category = get_model('catalogue', 'Category')
Course = get_model('courses', 'Course')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')

COUPONS_LINK = reverse('api:v2:coupons-list')


@httpretty.activate
@ddt.ddt
class CouponViewSetTest(CouponMixin, CourseCatalogTestMixin, TestCase):
    def setUp(self):
        super(CouponViewSetTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        course = CourseFactory(id='edx/Demo_Course/DemoX')
        self.seat = course.create_or_update_seat('verified', True, 50, self.partner)

        self.coupon_data = {
            'title': 'Test Coupon',
            'partner': self.partner,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'end_date': '2020-1-1',
            'code': '',
            'quantity': 2,
            'start_date': '2015-1-1',
            'voucher_type': Voucher.ONCE_PER_CUSTOMER,
            'categories': [self.category],
            'note': None,
            'max_uses': None,
            'catalog_query': None,
            'course_seat_types': ['verified'],
        }

    def setup_site_configuration(self):
        """ Helper method that creates a new Site object and assigns it a site configuration. """
        site_configuration = SiteConfigurationFactory(partner__name='TestX')
        site = SiteFactory()
        site.siteconfiguration = site_configuration
        return site

    @ddt.data(
        (Voucher.ONCE_PER_CUSTOMER, 2, 2),
        (Voucher.SINGLE_USE, 2, None)
    )
    @ddt.unpack
    def test_create(self, voucher_type, max_uses, expected_max_uses):
        """Test the create method."""
        title = 'Test coupon'
        self.coupon_data.update({
            'title': title,
            'client': 'Client',
            'voucher_type': voucher_type,
            'price': 100,
            'category_ids': [self.category.id],
            'max_uses': max_uses,
        })
        request = RequestFactory()
        request.user = self.user
        request.data = self.coupon_data
        request.site = self.site
        request.COOKIES = {}

        response = CouponViewSet().create(request)

        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(
            response.data,
            {'payment_data': {'payment_processor_name': 'Invoice'}, 'id': 1, 'order': 1, 'coupon_id': 3}
        )

        coupon = Product.objects.get(title=title)
        self.assertEqual(
            coupon.attr.coupon_vouchers.vouchers.first().offers.first().max_global_applications,
            expected_max_uses
        )

    def test_create_coupon_product(self):
        """Test the created coupon data."""
        coupon_price = 100
        quantity = 5
        title = 'Test coupon'
        coupon = self.create_coupon(price=coupon_price, quantity=quantity)

        self.assertEqual(Product.objects.filter(product_class=self.coupon_product_class).count(), 1)
        self.assertIsInstance(coupon, Product)
        self.assertEqual(coupon.title, title)

        self.assertEqual(StockRecord.objects.filter(product=coupon).count(), 1)
        stock_record = StockRecord.objects.get(product=coupon)
        self.assertEqual(stock_record.price_currency, settings.OSCAR_DEFAULT_CURRENCY)
        self.assertEqual(stock_record.price_excl_tax, coupon_price)

        self.assertEqual(coupon.attr.coupon_vouchers.vouchers.count(), quantity)
        category = ProductCategory.objects.get(product=coupon).category
        self.assertEqual(category, self.category)

    def test_custom_code_string(self):
        """Test creating a coupon with custom voucher code."""
        custom_code = 'CUSTOMCODE'
        self.coupon_data.update({
            'voucher_type': Voucher.ONCE_PER_CUSTOMER,
            'code': custom_code,
            'quantity': 1,
        })
        custom_coupon = CouponViewSet().create_coupon_product(
            title='Custom coupon',
            price=100,
            data=self.coupon_data
        )
        self.assertEqual(custom_coupon.attr.coupon_vouchers.vouchers.count(), self.coupon_data['quantity'])
        self.assertEqual(custom_coupon.attr.coupon_vouchers.vouchers.first().code, custom_code)

    def test_custom_code_integrity_error(self):
        """Test custom coupon code duplication."""
        self.coupon_data.update({
            'code': 'CUSTOMCODE',
            'quantity': 1,
        })
        CouponViewSet().create_coupon_product(
            title='Custom coupon',
            price=100,
            data=self.coupon_data
        )

        with self.assertRaises(IntegrityError):
            CouponViewSet().create_coupon_product(
                title='Coupon with integrity issue',
                price=100,
                data=self.coupon_data
            )

    def test_coupon_note(self):
        """Test creating a coupon with a note."""
        note = '𝑵𝑶𝑻𝑬'
        title = 'Coupon with note'
        self.coupon_data.update({
            'note': note,
        })
        note_coupon = CouponViewSet().create_coupon_product(
            title=title,
            price=100,
            data=self.coupon_data
        )
        self.assertEqual(note_coupon.attr.note, note)
        self.assertEqual(note_coupon.title, title)

    def test_multi_use_coupon_creation(self):
        """Test that the endpoint supports the creation of multi-usage coupons."""
        max_uses_number = 2
        self.coupon_data.update({
            'max_uses': max_uses_number,
        })
        coupon = CouponViewSet().create_coupon_product(
            title='Test coupon',
            price=100,
            data=self.coupon_data
        )
        voucher = coupon.attr.coupon_vouchers.vouchers.first()
        self.assertEqual(voucher.offers.first().max_global_applications, max_uses_number)

    def test_add_product_to_basket(self):
        """Test adding a coupon product to a basket."""
        price = 99
        self.create_coupon(price=price, partner=self.partner)

        self.assertIsInstance(self.basket, Basket)
        self.assertEqual(Basket.objects.count(), 1)
        self.assertEqual(self.basket.lines.count(), 1)
        self.assertEqual(self.basket.lines.first().price_excl_tax, price)

    def test_create_order(self):
        """Test the order creation."""
        price = 76
        self.create_coupon(price=price, partner=self.partner)

        self.assertEqual(self.response_data[AC.KEYS.BASKET_ID], 1)
        self.assertEqual(self.response_data[AC.KEYS.ORDER], 1)
        self.assertEqual(self.response_data[AC.KEYS.PAYMENT_DATA][AC.KEYS.PAYMENT_PROCESSOR_NAME], 'Invoice')

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.first().status, 'Complete')
        self.assertEqual(Order.objects.first().total_incl_tax, price)
        self.assertEqual(Basket.objects.first().status, 'Submitted')

    def test_create_update_data_dict(self):
        """Test the update data dictionary"""
        data = {}

        for field in AC.UPDATEABLE_VOUCHER_FIELDS:
            CouponViewSet().create_update_data_dict(
                request_data=self.coupon_data,
                request_data_key=field['request_data_key'],
                update_dict=data,
                update_dict_key=field['attribute']
            )

        self.assertDictEqual(data, {
            'end_datetime': self.coupon_data['end_date'],
            'start_datetime': self.coupon_data['start_date'],
            'name': self.coupon_data['title'],
        })

    def test_delete_coupon(self):
        """Test the coupon deletion."""
        quantity = 5
        coupon = self.create_coupon(quantity=quantity, partner=self.partner)
        self.assertEqual(Product.objects.filter(product_class=self.coupon_product_class).count(), 1)
        self.assertEqual(StockRecord.objects.filter(product=coupon).count(), 1)
        coupon_voucher_qs = CouponVouchers.objects.filter(coupon=coupon)
        self.assertEqual(coupon_voucher_qs.count(), 1)
        self.assertEqual(coupon_voucher_qs.first().vouchers.count(), quantity)

        request = RequestFactory()
        request.site = self.setup_site_configuration()
        response = CouponViewSet().destroy(request, coupon.id)

        self.assertEqual(Product.objects.filter(product_class=self.coupon_product_class).count(), 0)
        self.assertEqual(StockRecord.objects.filter(product=coupon).count(), 0)
        coupon_voucher_qs = CouponVouchers.objects.filter(coupon=coupon)
        self.assertEqual(coupon_voucher_qs.count(), 0)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(response.status_code, 204)

        response = CouponViewSet().destroy(request, 100)
        self.assertEqual(response.status_code, 404)


@ddt.ddt
class CouponViewSetFunctionalTest(CouponMixin, CourseCatalogTestMixin, CatalogPreviewMockMixin, TestCase):
    """Test the coupon order creation functionality."""

    def setUp(self):
        super(CouponViewSetFunctionalTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.course, __ = self.create_course_and_seat(course_id='edx/Demo_Course1/DemoX', price=50)
        self.data = {
            'title': 'Test coupon',
            'client': 'TestX',
            'start_date': '2015-01-01',
            'end_date': '2020-01-01',
            'code': '',
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'voucher_type': Voucher.SINGLE_USE,
            'quantity': 2,
            'price': 100,
            'category_ids': [self.category.id],
            'catalog_query': None,
            'course_seat_types': ['verified'],
        }
        self.response = self.client.post(COUPONS_LINK, data=self.data, format='json')

    def get_response_json(self, method, path, data=None):
        """Helper method for sending requests and returning JSON response content."""
        if method == 'GET':
            response = self.client.get(path)
        elif method == 'POST':
            response = self.client.post(path, json.dumps(data), 'application/json')
        elif method == 'PUT':
            response = self.client.put(path, json.dumps(data), 'application/json')
        return json.loads(response.content)

    def test_response(self):
        """Test the response data given after the order was created."""
        self.assertEqual(self.response.status_code, 200)
        response_data = json.loads(self.response.content)
        coupon = Product.objects.latest()
        basket = Basket.objects.latest()
        order = Order.objects.latest()

        self.assertEqual(response_data[AC.KEYS.COUPON_ID], coupon.id)
        self.assertEqual(response_data[AC.KEYS.BASKET_ID], basket.id)
        self.assertEqual(response_data[AC.KEYS.ORDER], order.id)
        self.assertEqual(response_data[AC.KEYS.PAYMENT_DATA][AC.KEYS.PAYMENT_PROCESSOR_NAME], 'Invoice')

    def test_order(self):
        """Test the order data after order creation."""
        self.assertEqual(Order.objects.count(), 1)
        order = Order.objects.latest()
        self.assertEqual(order.status, 'Complete')
        self.assertEqual(order.lines.count(), 1)
        self.assertEqual(order.lines.first().product.title, self.data['title'])

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
        coupon_data = json.loads(response.content)['results'][0]
        self.assertEqual(coupon_data['title'], self.data['title'])

    def update_coupon(self, update_data):
        """ Helper method for updating a coupon.

        Arguments:
            update_data (dict): A dictionary with the fields for update.

        Returns:
            The coupon product object and the update request response data.
        """
        coupon = Product.objects.latest()
        response_data = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id}),
            data=update_data
        )
        return coupon, response_data

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_update(self):
        """Test updating a coupon."""
        self.mock_dynamic_catalog_course_runs_api(query=self.data['catalog_query'], course_run=self.course)
        new_title = 'New title'
        coupon, response_data = self.update_coupon({'title': new_title})

        self.assertEqual(response_data['id'], coupon.id)
        self.assertEqual(response_data['title'], new_title)

        vouchers = coupon.attr.coupon_vouchers.vouchers.all()
        for voucher in vouchers:
            self.assertEqual(voucher.name, new_title)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_update_datetimes(self):
        """Test that updating a coupons date updates all of it's voucher dates."""
        self.mock_dynamic_catalog_course_runs_api(query=self.data['catalog_query'], course_run=self.course)
        start_date = datetime.datetime(2030, 1, 1, tzinfo=pytz.UTC)
        end_date = datetime.datetime(2035, 1, 1, tzinfo=pytz.UTC)
        coupon, response_data = self.update_coupon({
            AC.KEYS.START_DATE: start_date.isoformat(),
            AC.KEYS.END_DATE: end_date.isoformat()
        })
        self.assertEqual(response_data['id'], coupon.id)

        vouchers = coupon.attr.coupon_vouchers.vouchers.all()
        for voucher in vouchers:
            self.assertEqual(voucher.start_datetime, start_date)
            self.assertEqual(voucher.end_datetime, end_date)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_update_benefit_value(self):
        """Test that updating a benefit value updates all of it's voucher offers."""
        self.mock_dynamic_catalog_course_runs_api(query=self.data['catalog_query'], course_run=self.course)
        new_benefit_value = 50
        coupon, __ = self.update_coupon({
            AC.KEYS.BENEFIT_VALUE: new_benefit_value
        })

        vouchers = coupon.attr.coupon_vouchers.vouchers.all()
        for voucher in vouchers:
            self.assertEqual(voucher.offers.first().benefit.value, Decimal(new_benefit_value))

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_update_category(self):
        """Test updating a coupon's category."""
        self.mock_dynamic_catalog_course_runs_api(query=self.data['catalog_query'], course_run=self.course)
        category = factories.CategoryFactory()
        coupon, __ = self.update_coupon({
            AC.KEYS.CATEGORY_IDS: [category.id]
        })
        coupon_categories = ProductCategory.objects.filter(product=coupon).values_list('category', flat=True)
        self.assertIn(category.id, coupon_categories)
        self.assertEqual(len(coupon_categories), 1)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_update_client(self):
        """Test updating a coupon's client."""
        self.mock_dynamic_catalog_course_runs_api(query=self.data['catalog_query'], course_run=self.course)
        new_client_name = 'Client 123'
        coupon, __ = self.update_coupon({
            AC.KEYS.CLIENT: new_client_name
        })
        invoice = Invoice.objects.get(order__basket__lines__product=coupon)
        self.assertEqual(invoice.business_client.name, new_client_name)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_update_coupon_price(self):
        """Test updating a coupon's price."""
        self.mock_dynamic_catalog_course_runs_api(query=self.data['catalog_query'], course_run=self.course)
        new_price = 77
        coupon, __ = self.update_coupon({
            AC.KEYS.PRICE: new_price
        })
        self.assertEqual(StockRecord.objects.get(product=coupon).price_excl_tax, new_price)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_update_note(self):
        """Test updating a coupon's note."""
        self.mock_dynamic_catalog_course_runs_api(query=self.data['catalog_query'], course_run=self.course)
        new_note = 'This is the test note.'
        coupon, __ = self.update_coupon({
            AC.KEYS.NOTE: new_note
        })
        self.assertEqual(coupon.attr.note, new_note)

    def test_update_coupon_benefit_value(self):
        """Test updating the benefit value of the coupon vouchers."""
        coupon = Product.objects.latest()
        vouchers = coupon.attr.coupon_vouchers.vouchers.all()
        new_benefit_value = Decimal(54)

        CouponViewSet().update_coupon_benefit_value(
            benefit_value=new_benefit_value,
            vouchers=vouchers,
            coupon=coupon
        )
        for voucher in vouchers:
            self.assertEqual(voucher.offers.first().benefit.value, new_benefit_value)

    def test_update_coupon_category(self):
        """Test updating a coupon's category."""
        coupon = Product.objects.latest()
        category = factories.CategoryFactory()
        CouponViewSet().update_coupon_category(
            category_ids=[category.id],
            coupon=coupon
        )

        coupon_categories = ProductCategory.objects.filter(product=coupon).values_list('category', flat=True)
        self.assertIn(category.id, coupon_categories)
        self.assertEqual(len(coupon_categories), 1)

    def test_update_coupon_client(self):
        """Test updating a coupon's client."""
        coupon = Product.objects.latest()
        new_client_name = 'Test Client Username'
        baskets = Basket.objects.filter(lines__product=coupon)
        basket = baskets.first()
        CouponViewSet().update_coupon_client(
            baskets=baskets,
            client_username=new_client_name
        )

        invoice = Invoice.objects.get(order__basket=basket)
        self.assertEqual(invoice.business_client.name, new_client_name)

        # To test the old coupon clients, we need to delete all basket orders.
        Order.objects.filter(basket__in=baskets).delete()
        CouponViewSet().update_coupon_client(
            baskets=baskets,
            client_username=new_client_name
        )

        baskets = Basket.objects.filter(lines__product_id=coupon.id)
        self.assertEqual(baskets.first().owner.username, new_client_name)

    @ddt.data('audit', 'honor')
    def test_restricted_course_mode(self, mode):
        """Test that an exception is raised when a black-listed course mode is used."""
        self.data.update({'course_seat_types': [mode]})
        response = self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_dynamic_catalog_coupon(self):
        """ Verify dynamic range values are returned. """
        catalog_query = 'key:*'
        course_seat_types = ['verified']
        self.data.update({
            'title': 'Dynamic coupon',
            'catalog_query': catalog_query,
            'course_seat_types': course_seat_types,
        })
        course, seat = self.create_course_and_seat(course_id='dynamic/catalog/coupon')
        self.mock_dynamic_catalog_course_runs_api(query=catalog_query, course_run=course)

        coupon_id = self.get_response_json('POST', COUPONS_LINK, self.data)['coupon_id']
        details = self.get_response_json('GET', reverse('api:v2:coupons-detail', args=[coupon_id]))
        self.assertEqual(details['catalog_query'], catalog_query)
        self.assertEqual(details['course_seat_types'], course_seat_types)
        self.assertEqual(details['seats'][0]['id'], seat.id)

    @ddt.data(
        (Voucher.SINGLE_USE, None),
        (Voucher.ONCE_PER_CUSTOMER, 2),
        (Voucher.MULTI_USE, 2)
    )
    @ddt.unpack
    def test_multi_use_single_use_coupon(self, voucher_type, max_uses):
        """Test that a SINGLE_USE coupon has the default max_uses value and others the set one. """
        self.data.update({
            'max_uses': max_uses,
            'voucher_type': voucher_type,
        })
        self.client.post(COUPONS_LINK, data=self.data, format='json')
        coupon = Product.objects.latest()
        voucher = coupon.attr.coupon_vouchers.vouchers.first()
        self.assertEquals(voucher.usage, voucher_type)
        self.assertEquals(voucher.offers.first().max_global_applications, max_uses)

    def update_prepaid_invoice_data(self):
        """ Update the 'data' class variable with invoice information. """
        invoice_data = {
            'invoice_type': Invoice.PREPAID,
            'invoice_number': 'INV-00001',
            'invoice_payment_date': datetime.datetime(2015, 1, 1, tzinfo=pytz.UTC).isoformat(),
            'invoice_discount_type': None,
            'invoice_discount_value': None
        }
        self.data.update(invoice_data)

    def assert_invoice_serialized_data(self, coupon_data):
        """ Assert that the coupon details show the invoice data. """
        invoice_details = coupon_data['payment_information']['Invoice']
        self.assertEqual(invoice_details['type'], self.data['invoice_type'])
        self.assertEqual(invoice_details['number'], self.data['invoice_number'])
        self.assertEqual(invoice_details['discount_type'], self.data['invoice_discount_type'])
        self.assertEqual(invoice_details['discount_value'], self.data['invoice_discount_value'])

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_coupon_with_invoice_data(self):
        """ Verify an invoice is created with the proper data. """
        self.mock_dynamic_catalog_course_runs_api(query=self.data['catalog_query'], course_run=self.course)
        self.update_prepaid_invoice_data()
        response = self.get_response_json('POST', COUPONS_LINK, data=self.data)
        invoice = Invoice.objects.get(order__basket__lines__product__id=response['coupon_id'])
        self.assertEqual(invoice.type, self.data['invoice_type'])
        self.assertEqual(invoice.number, self.data['invoice_number'])
        self.assertEqual(invoice.payment_date.isoformat(), self.data['invoice_payment_date'])
        details = self.get_response_json('GET', reverse('api:v2:coupons-detail', args=[response['coupon_id']]))
        self.assert_invoice_serialized_data(details)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_coupon_invoice_update(self):
        """ Verify a coupon is updated with new invoice data. """
        self.mock_dynamic_catalog_course_runs_api(query=self.data['catalog_query'], course_run=self.course)
        self.update_prepaid_invoice_data()
        response = self.get_response_json('POST', COUPONS_LINK, data=self.data)
        details = self.get_response_json('GET', reverse('api:v2:coupons-detail', args=[response['coupon_id']]))
        self.assert_invoice_serialized_data(details)

        invoice_postpaid_data = {
            'invoice_type': Invoice.POSTPAID,
            'invoice_number': None,
            'invoice_payment_date': None,
            'invoice_discount_type': Invoice.PERCENTAGE,
            'invoice_discount_value': 33,
        }
        self.data.update(invoice_postpaid_data)
        updated_coupon = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': response['coupon_id']}),
            data=self.data
        )
        self.assert_invoice_serialized_data(updated_coupon)


class CouponCategoriesListViewTests(TestCase):
    """ Tests for the coupon category list view. """
    path = reverse('api:v2:coupons:coupons_categories')

    def setUp(self):
        super(CouponCategoriesListViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        Category.objects.all().delete()
        create_from_breadcrumbs('Coupons > Coupon test category')

    def test_category_list(self):
        """ Verify the endpoint returns successfully. """
        response = self.client.get(self.path)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['count'], 1)
        self.assertEqual(response_data['results'][0]['name'], 'Coupon test category')
