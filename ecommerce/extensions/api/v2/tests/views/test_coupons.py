# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import datetime
from decimal import Decimal

import ddt
import httpretty
from django.core.urlresolvers import reverse
from django.db.utils import IntegrityError
from django.test import RequestFactory
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_class, get_model
from oscar.test import factories
import pytz
from rest_framework import status

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.coupons.tests.mixins import CatalogPreviewMockMixin, CouponMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.invoice.models import Invoice
from ecommerce.tests.factories import ProductFactory, SiteConfigurationFactory, SiteFactory
from ecommerce.tests.mixins import ThrottlingMixin
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.utils', 'Applicator')
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


@httpretty.activate
@ddt.ddt
class CouponViewSetTest(CouponMixin, CourseCatalogTestMixin, TestCase):
    def setUp(self):
        super(CouponViewSetTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        course = CourseFactory(id='edx/Demo_Course/DemoX')
        self.seat = course.create_or_update_seat('verified', True, 50, self.partner)

        self.catalog = Catalog.objects.create(partner=self.partner)
        self.coupon_data = {
            'title': 'Test Coupon',
            'partner': self.partner,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'catalog': self.catalog,
            'end_date': '2020-1-1',
            'code': '',
            'quantity': 2,
            'start_date': '2015-1-1',
            'voucher_type': Voucher.ONCE_PER_CUSTOMER,
            'categories': [self.category],
            'note': None,
            'max_uses': None,
            'catalog_query': None,
            'course_seat_types': None,
        }

    def setup_site_configuration(self):
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
        stock_record = self.seat.stockrecords.first()
        self.coupon_data.update({
            'title': title,
            'client_username': 'Client',
            'stock_record_ids': [stock_record.id],
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
        coupon = self.create_coupon()
        self.assertEqual(Product.objects.filter(product_class=self.coupon_product_class).count(), 1)
        self.assertIsInstance(coupon, Product)
        self.assertEqual(coupon.title, 'Test coupon')

        self.assertEqual(StockRecord.objects.filter(product=coupon).count(), 1)
        stock_record = StockRecord.objects.get(product=coupon)
        self.assertEqual(stock_record.price_currency, 'USD')
        self.assertEqual(stock_record.price_excl_tax, 100)

        self.assertEqual(coupon.attr.coupon_vouchers.vouchers.count(), 5)
        category = ProductCategory.objects.get(product=coupon).category
        self.assertEqual(category, self.category)

    def test_custom_code_string(self):
        """Test creating a coupon with custom voucher code."""
        self.coupon_data.update({
            'voucher_type': Voucher.ONCE_PER_CUSTOMER,
            'code': 'CUSTOMCODE',
            'quantity': 1,
        })
        custom_coupon = CouponViewSet().create_coupon_product(
            title='Custom coupon',
            price=100,
            data=self.coupon_data
        )
        self.assertEqual(custom_coupon.attr.coupon_vouchers.vouchers.count(), 1)
        self.assertEqual(custom_coupon.attr.coupon_vouchers.vouchers.first().code, 'CUSTOMCODE')

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
        self.coupon_data.update({
            'note': '𝑵𝑶𝑻𝑬',
        })
        note_coupon = CouponViewSet().create_coupon_product(
            title='Coupon',
            price=100,
            data=self.coupon_data
        )
        self.assertEqual(note_coupon.attr.note, '𝑵𝑶𝑻𝑬')
        self.assertEqual(note_coupon.title, 'Coupon')

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
        self.create_coupon(partner=self.partner)

        self.assertIsInstance(self.basket, Basket)
        self.assertEqual(Basket.objects.count(), 1)
        self.assertEqual(self.basket.lines.count(), 1)
        self.assertEqual(self.basket.lines.first().price_excl_tax, 100)

    def test_create_order(self):
        """Test the order creation."""
        self.create_coupon(partner=self.partner)

        self.assertEqual(self.response_data[AC.KEYS.BASKET_ID], 1)
        self.assertEqual(self.response_data[AC.KEYS.ORDER], 1)
        self.assertEqual(self.response_data[AC.KEYS.PAYMENT_DATA][AC.KEYS.PAYMENT_PROCESSOR_NAME], 'Invoice')

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.first().status, 'Complete')
        self.assertEqual(Order.objects.first().total_incl_tax, 100)
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
        coupon = self.create_coupon(partner=self.partner)
        self.assertEqual(Product.objects.filter(product_class=self.coupon_product_class).count(), 1)
        self.assertEqual(StockRecord.objects.filter(product=coupon).count(), 1)
        coupon_voucher_qs = CouponVouchers.objects.filter(coupon=coupon)
        self.assertEqual(coupon_voucher_qs.count(), 1)
        self.assertEqual(coupon_voucher_qs.first().vouchers.count(), 5)

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
class CouponViewSetFunctionalTest(CouponMixin, CourseCatalogTestMixin, CatalogPreviewMockMixin, ThrottlingMixin,
                                  TestCase):
    """Test the coupon order creation functionality."""

    def setUp(self):
        super(CouponViewSetFunctionalTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.create_course_and_seat(course_id='edx/Demo_Course1/DemoX', price=50)
        self.create_course_and_seat(course_id='edx/Demo_Course2/DemoX', price=100)
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
            'category_ids': [self.category.id],
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
        coupon_data = json.loads(response.content)['results'][0]
        self.assertEqual(coupon_data['title'], 'Test coupon')

    def get_response_json(self, method, path, data=None):
        if method == 'GET':
            response = self.client.get(path)
        elif method == 'POST':
            response = self.client.post(path, json.dumps(data), 'application/json')
        elif method == 'PUT':
            response = self.client.put(path, json.dumps(data), 'application/json')
        return json.loads(response.content)

    def test_update(self):
        """Test updating a coupon."""
        coupon = Product.objects.get(title='Test coupon')
        response_data = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id}),
            data={'title': 'New title'}
        )
        self.assertEqual(response_data['id'], coupon.id)
        self.assertEqual(response_data['title'], 'New title')

    def test_update_title(self):
        """Test updating a coupon's title."""
        coupon = Product.objects.get(title='Test coupon')
        data = {
            'id': coupon.id,
            AC.KEYS.TITLE: 'New title'
        }
        response_data = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id}),
            data=data
        )
        self.assertEqual(response_data['id'], coupon.id)

        new_coupon = Product.objects.get(id=coupon.id)
        vouchers = new_coupon.attr.coupon_vouchers.vouchers.all()
        for voucher in vouchers:
            self.assertEqual(voucher.name, 'New title')

    def test_update_datetimes(self):
        """Test that updating a coupons date updates all of it's voucher dates."""
        coupon = Product.objects.get(title='Test coupon')
        data = {
            'id': coupon.id,
            AC.KEYS.START_DATE: '2030-01-01',
            AC.KEYS.END_DATE: '2035-01-01'
        }
        response_data = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id}),
            data=data
        )
        self.assertEqual(response_data['id'], coupon.id)

        new_coupon = Product.objects.get(id=coupon.id)
        vouchers = new_coupon.attr.coupon_vouchers.vouchers.all()
        for voucher in vouchers:
            self.assertEqual(voucher.start_datetime.year, 2030)
            self.assertEqual(voucher.end_datetime.year, 2035)

    def test_update_benefit_value(self):
        """Test that updating a benefit value updates all of it's voucher offers."""
        coupon = Product.objects.get(title='Test coupon')
        path = reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id})
        data = {
            'id': coupon.id,
            AC.KEYS.BENEFIT_VALUE: 50
        }
        self.client.put(path, json.dumps(data), 'application/json')

        new_coupon = Product.objects.get(id=coupon.id)
        vouchers = new_coupon.attr.coupon_vouchers.vouchers.all()
        for voucher in vouchers:
            self.assertEqual(voucher.offers.first().benefit.value, Decimal(50.0))

    def test_update_category(self):
        coupon = Product.objects.get(title='Test coupon')
        category = factories.CategoryFactory()
        path = reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id})
        data = {
            'id': coupon.id,
            AC.KEYS.CATEGORY_IDS: [category.id]
        }
        self.client.put(path, json.dumps(data), 'application/json')

        new_coupon = Product.objects.get(id=coupon.id)
        coupon_categories = ProductCategory.objects.filter(product=new_coupon).values_list('category', flat=True)
        self.assertIn(category.id, coupon_categories)
        self.assertEqual(len(coupon_categories), 1)

    def test_update_client(self):
        coupon = Product.objects.get(title='Test coupon')
        path = reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id})
        data = {
            'id': coupon.id,
            AC.KEYS.CLIENT_USERNAME: 'Client 123'
        }
        self.client.put(path, json.dumps(data), 'application/json')

        new_coupon = Product.objects.get(id=coupon.id)
        basket = Basket.objects.filter(lines__product_id=new_coupon.id).first()
        invoice = Invoice.objects.get(order__basket=basket)
        self.assertEqual(invoice.business_client.name, 'Client 123')

    def test_update_coupon_price(self):
        """Test that updating the price updates all of it's stock record prices."""
        coupon = Product.objects.get(title='Test coupon')
        path = reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id})
        data = {
            'id': coupon.id,
            AC.KEYS.PRICE: 77
        }
        self.client.put(path, json.dumps(data), 'application/json')

        new_coupon = Product.objects.get(id=coupon.id)
        stock_records = StockRecord.objects.filter(product=new_coupon).all()
        for stock_record in stock_records:
            self.assertEqual(stock_record.price_excl_tax, 77)

    def test_update_note(self):
        coupon = Product.objects.get(title='Test coupon')
        path = reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id})
        data = {
            'id': coupon.id,
            AC.KEYS.NOTE: 'This is the test note.'
        }
        self.client.put(path, json.dumps(data), 'application/json')

        new_coupon = Product.objects.get(id=coupon.id)
        self.assertEqual(new_coupon.attr.note, 'This is the test note.')

    def test_update_coupon_benefit_value(self):
        coupon = Product.objects.get(title='Test coupon')
        vouchers = coupon.attr.coupon_vouchers.vouchers.all()
        CouponViewSet().update_coupon_benefit_value(
            benefit_value=Decimal(54),
            vouchers=vouchers,
            coupon=coupon
        )

        for voucher in vouchers:
            self.assertEqual(voucher.offers.first().benefit.value, Decimal(54))

    def test_update_coupon_category(self):
        coupon = Product.objects.get(title='Test coupon')
        category = factories.CategoryFactory()
        CouponViewSet().update_coupon_category(
            category_ids=[category.id],
            coupon=coupon
        )

        coupon_categories = ProductCategory.objects.filter(product=coupon).values_list('category', flat=True)
        self.assertIn(category.id, coupon_categories)
        self.assertEqual(len(coupon_categories), 1)

    def test_update_coupon_client(self):
        coupon = Product.objects.get(title='Test coupon')
        baskets = Basket.objects.filter(lines__product_id=coupon.id)
        basket = baskets.first()
        CouponViewSet().update_coupon_client(
            baskets=baskets,
            client_username='Test Client Username'
        )

        invoice = Invoice.objects.get(order__basket=basket)
        self.assertEqual(invoice.business_client.name, 'Test Client Username')

        # To test the old coupon clients, we need to delete all basket orders
        Order.objects.filter(basket__in=baskets).delete()
        CouponViewSet().update_coupon_client(
            baskets=baskets,
            client_username='Test Client Username'
        )

        baskets = Basket.objects.filter(lines__product_id=coupon.id)
        self.assertEqual(baskets.first().owner.username, 'Test Client Username')

    @ddt.data('audit', 'honor')
    def test_restricted_course_mode(self, mode):
        """Test that an exception is raised when a black-listed course mode is used."""
        course = CourseFactory(id='black/list/mode')
        seat = course.create_or_update_seat(mode, False, 0, self.partner)
        # Seats derived from a migrated "audit" mode do not have a certificate_type attribute.
        if mode == 'audit':
            seat = ProductFactory()
        self.data.update({'stock_record_ids': [StockRecord.objects.get(product=seat).id]})
        response = self.client.post(COUPONS_LINK, data=self.data, format='json')
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
        self.data.pop('stock_record_ids')
        course, seat = self.create_course_and_seat(course_id='dynamic/catalog/coupon')
        self.mock_dynamic_catalog_course_runs_api(query=catalog_query, course_run=course)

        response = self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        coupon_id = json.loads(response.content)['coupon_id']
        details_response = self.client.get(reverse('api:v2:coupons-detail', args=[coupon_id]))
        detail = json.loads(details_response.content)
        self.assertEqual(detail['catalog_query'], catalog_query)
        self.assertEqual(detail['course_seat_types'], course_seat_types)
        self.assertEqual(detail['seats'][0]['id'], seat.id)

    def update_invoice_data(self):
        """ Update the 'data' class variable with invoice information. """
        invoice_data = {
            'invoice_type': 'Prepaid',
            'invoice_number': 'INV-00001',
            'invoiced_amount': 1000,
            'invoice_payment_date': datetime.datetime(2015, 1, 1, tzinfo=pytz.UTC).isoformat(),
        }
        self.data.update(invoice_data)

    def assert_invoice_data(self, coupon_id):
        """ Assert that the coupon details show the invoice data. """
        details = self.get_response_json('GET', reverse('api:v2:coupons-detail', args=[coupon_id]))
        invoice_details = details['payment_information']['Invoice']
        self.assertEqual(invoice_details['invoice_type'], self.data['invoice_type'])
        self.assertEqual(invoice_details['number'], self.data['invoice_number'])
        self.assertEqual(invoice_details['invoiced_amount'], self.data['invoiced_amount'])

    def test_coupon_with_invoice_data(self):
        """ Verify an invoice is created with the proper data. """
        self.update_invoice_data()
        response = self.get_response_json('POST', COUPONS_LINK, data=self.data)
        invoice = Invoice.objects.get(order__basket__lines__product__id=response['coupon_id'])
        self.assertEqual(invoice.invoice_type, self.data['invoice_type'])
        self.assertEqual(invoice.number, self.data['invoice_number'])
        self.assertEqual(invoice.invoiced_amount, self.data['invoiced_amount'])
        self.assertEqual(invoice.invoice_payment_date.isoformat(), self.data['invoice_payment_date'])
        self.assert_invoice_data(response['coupon_id'])

    def test_coupon_invoice_update(self):
        """ Verify a coupon is updated with new invoice data. """
        self.update_invoice_data()
        response = self.get_response_json('POST', COUPONS_LINK, data=self.data)
        self.assert_invoice_data(response['coupon_id'])

        new_invoice_data = {
            'invoice_type': 'Postpaid',
            'invoice_discount_type': 'Percentage',
            'invoice_discount_value': 1500,
        }
        self.data.update(new_invoice_data)
        updated_coupon = self.get_response_json('POST', COUPONS_LINK, data=self.data)
        self.assert_invoice_data(updated_coupon['coupon_id'])


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
