# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json
import datetime
from decimal import Decimal

import ddt
import httpretty
import pytz
from django.core.urlresolvers import reverse
from django.test import RequestFactory
from django.utils.timezone import now
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from rest_framework import status

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.coupons.tests.mixins import CourseCatalogMockMixin, CouponMixin
from ecommerce.courses.tests.factories import CourseFactory
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
Range = get_model('offer', 'Range')
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
            'title': 'Tešt Čoupon',
            'partner': self.partner,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'catalog': self.catalog,
            'end_datetime': str(now() + datetime.timedelta(days=10)),
            'code': '',
            'quantity': 2,
            'start_datetime': str(now() - datetime.timedelta(days=1)),
            'voucher_type': Voucher.ONCE_PER_CUSTOMER,
            'category': {'name': self.category.name},
            'note': None,
            'max_uses': None,
            'catalog_query': None,
            'course_seat_types': None,
            'email_domains': None,
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
            'client': 'Člient',
            'stock_record_ids': [stock_record.id],
            'voucher_type': voucher_type,
            'price': 100,
            'category': {'name': self.category.name},
            'max_uses': max_uses,
        })
        request = RequestFactory()
        request.user = self.user
        request.data = self.coupon_data
        request.site = self.site
        request.COOKIES = {}

        view = CouponViewSet()
        view.request = request
        response = view.create(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
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

    def test_creating_multi_offer_coupon(self):
        """Test the creation of a multi-offer coupon."""
        ordinary_coupon = self.create_coupon(quantity=2)
        ordinary_coupon_vouchers = ordinary_coupon.attr.coupon_vouchers.vouchers.all()
        self.assertEqual(
            ordinary_coupon_vouchers[0].offers.first(),
            ordinary_coupon_vouchers[1].offers.first()
        )

        multi_offer_coupon = self.create_coupon(quantity=2, voucher_type=Voucher.MULTI_USE)
        multi_offer_coupon_vouchers = multi_offer_coupon.attr.coupon_vouchers.vouchers.all()
        first_offer = multi_offer_coupon_vouchers[0].offers.first()
        second_offer = multi_offer_coupon_vouchers[1].offers.first()

        self.assertNotEqual(first_offer, second_offer)

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

        self.assertDictEqual(
            self.response_data,
            {'payment_data': {'payment_processor_name': 'Invoice'}, 'id': 1, 'order': 1, 'coupon_id': 3}
        )

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.first().status, 'Complete')
        self.assertEqual(Order.objects.first().total_incl_tax, 100)
        self.assertEqual(Basket.objects.first().status, 'Submitted')

    def test_create_update_data_dict(self):
        """Test creating update data dictionary"""
        fields = ['title', 'start_datetime', 'end_datetime']

        data = CouponViewSet().create_update_data_dict(
            data=self.coupon_data,
            fields=fields
        )

        self.assertDictEqual(data, {
            'end_datetime': self.coupon_data['end_datetime'],
            'start_datetime': self.coupon_data['start_datetime'],
            'title': self.coupon_data['title'],
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
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = CouponViewSet().destroy(request, 100)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@ddt.ddt
class CouponViewSetFunctionalTest(CouponMixin, CourseCatalogTestMixin, CourseCatalogMockMixin, ThrottlingMixin,
                                  TestCase):
    """Test the coupon order creation functionality."""

    def setUp(self):
        super(CouponViewSetFunctionalTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.create_course_and_seat(course_id='edx/Demo_Course1/DemoX', price=50)
        self.create_course_and_seat(course_id='edx/Demo_Course2/DemoX', price=100)
        self.data = {
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'category': {'name': self.category.name},
            'client': 'TeštX',
            'code': '',
            'end_datetime': str(now() + datetime.timedelta(days=10)),
            'price': 100,
            'quantity': 2,
            'start_datetime': str(now() - datetime.timedelta(days=10)),
            'stock_record_ids': [1, 2],
            'title': 'Tešt čoupon',
            'voucher_type': Voucher.SINGLE_USE
        }
        self.response = self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        self.coupon = Product.objects.get(title=self.data['title'])

    def get_response_json(self, method, path, data=None):
        """Helper method for sending requests and returning JSON response content."""
        if method == 'GET':
            response = self.client.get(path)
        elif method == 'POST':
            response = self.client.post(path, json.dumps(data), 'application/json')
        elif method == 'PUT':
            response = self.client.put(path, json.dumps(data), 'application/json')
        return json.loads(response.content)

    def _get_voucher_range_with_updated_dynamic_catalog_values(self):
        """Helper method for updating dynamic catalog values."""
        path = reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id})
        data = {
            'catalog_query': '*:*',
            'course_seat_types': ['verified'],
        }
        self.client.put(path, json.dumps(data), 'application/json')
        new_coupon = Product.objects.get(id=self.coupon.id)
        vouchers = new_coupon.attr.coupon_vouchers.vouchers
        return vouchers.first().offers.first().benefit.range, data

    def test_create_serializer_data(self):
        """Test if coupon serializer creates data for details page"""
        details_response = self.get_response_json(
            'GET',
            reverse('api:v2:coupons-detail', args=[self.coupon.id]),
            data=self.data
        )
        self.assertEqual(details_response['coupon_type'], 'Enrollment code')
        self.assertEqual(details_response['code_status'], 'ACTIVE')

    def test_create_coupon_product_invalid_category_data(self):
        """Test creating coupon when provided category data is invalid."""
        self.data.update({'category': {'id': 10000, 'name': 'Category Not Found'}})
        response_data = self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        self.assertEqual(response_data.status_code, status.HTTP_404_NOT_FOUND)

    @ddt.data(
        ('benefit_type', ['', 'Incorrect benefit type']),
        ('benefit_value', ['', 'Incorrect benefit value', -1, 101]),
        ('category', [{'a': 'a', 'b': 'b'}]),
    )
    @ddt.unpack
    def test_create_coupon_product_invalid_data(self, key, values):
        """Test creating coupon when provided data is invalid."""
        for value in values:
            self.data.update({key: value})
            response_data = self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
            self.assertEqual(response_data.status_code, status.HTTP_400_BAD_REQUEST)

    @ddt.data('benefit_type', 'benefit_value')
    def test_create_coupon_product_no_data_provided(self, key):
        """Test creating coupon when data is not provided in json."""
        del self.data[key]
        response_data = self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        self.assertEqual(response_data.status_code, status.HTTP_400_BAD_REQUEST)

    def test_response(self):
        """Test the response data given after the order was created."""
        self.assertEqual(self.response.status_code, status.HTTP_200_OK)
        response_data = json.loads(self.response.content)
        self.assertDictEqual(
            response_data,
            {'payment_data': {'payment_processor_name': 'Invoice'}, 'id': 1, 'order': 1, 'coupon_id': 5}
        )

    def test_order(self):
        """Test the order data after order creation."""
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.first().status, 'Complete')
        self.assertEqual(Order.objects.first().lines.count(), 1)
        self.assertEqual(Order.objects.first().lines.first().product, self.coupon)

    def test_authentication_required(self):
        """Test that a guest cannot access the view."""
        response = self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.logout()
        response = self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authorization_required(self):
        """Test that a non-staff user cannot access the view."""
        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)

        response = self.client.post(COUPONS_LINK, data=self.data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_coupons(self):
        """Test that the endpoint returns information needed for the details page."""
        response = self.client.get(COUPONS_LINK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        coupon_data = json.loads(response.content)['results'][0]
        self.assertEqual(coupon_data['title'], self.data['title'])
        self.assertEqual(coupon_data['category']['name'], self.data['category']['name'])
        self.assertEqual(coupon_data['client'], self.data['client'])

    def test_list_and_details_endpoint_return_custom_code(self):
        """Test that the list and details endpoints return the correct code."""
        self.data.update({
            'benefit_value': 50,
            'code': '123456',
            'quantity': 1,
            'title': 'Tešt čoupon 2'
        })
        self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        coupon = Product.objects.get(title=self.data['title'])
        details_response = self.get_response_json(
            'GET',
            reverse('api:v2:coupons-detail', args=[coupon.id]),
            data=self.data
        )
        self.assertEqual(details_response['code'], self.data['code'])
        self.assertEqual(details_response['coupon_type'], 'Discount code')

        list_response = self.client.get(COUPONS_LINK)
        coupon_data = json.loads(list_response.content)['results'][0]
        self.assertEqual(coupon_data['code'], self.data['code'])

    def test_already_existing_code(self):
        """Test custom coupon code duplication."""
        self.data.update({
            'code': 'CUSTOMCODE',
            'quantity': 1,
        })
        self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        response = self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update(self):
        """Test updating a coupon."""
        response_data = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id}),
            data={'title': 'New title'}
        )
        self.assertEqual(response_data['id'], self.coupon.id)
        self.assertEqual(response_data['title'], 'New title')
        self.assertIsNone(response_data['email_domains'])

    def test_update_name(self):
        """Test updating voucher name."""
        data = {
            'id': self.coupon.id,
            'name': 'New voucher name'
        }
        response_data = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id}),
            data=data
        )
        self.assertEqual(response_data['id'], self.coupon.id)

        new_coupon = Product.objects.get(id=self.coupon.id)
        vouchers = new_coupon.attr.coupon_vouchers.vouchers.all()
        for voucher in vouchers:
            self.assertEqual(voucher.name, 'New voucher name')

    def test_update_datetimes(self):
        """Test that updating a coupons date updates all of it's voucher dates."""
        data = {
            'id': self.coupon.id,
            'start_datetime': '2030-01-01',
            'end_datetime': '2035-01-01'
        }
        response_data = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id}),
            data=data
        )
        self.assertEqual(response_data['id'], self.coupon.id)

        new_coupon = Product.objects.get(id=self.coupon.id)
        vouchers = new_coupon.attr.coupon_vouchers.vouchers.all()
        for voucher in vouchers:
            self.assertEqual(voucher.start_datetime.year, 2030)
            self.assertEqual(voucher.end_datetime.year, 2035)

    def test_update_benefit_value(self):
        """Test that updating a benefit value updates all of it's voucher offers."""
        path = reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id})
        data = {
            'id': self.coupon.id,
            'benefit_value': 50
        }
        self.client.put(path, json.dumps(data), 'application/json')

        new_coupon = Product.objects.get(id=self.coupon.id)
        vouchers = new_coupon.attr.coupon_vouchers.vouchers.all()
        for voucher in vouchers:
            self.assertEqual(voucher.offers.first().benefit.value, Decimal(50.0))

    def test_update_category(self):
        category = factories.CategoryFactory()
        path = reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id})
        data = {
            'id': self.coupon.id,
            'category': {'name': category.name}
        }
        self.client.put(path, json.dumps(data), 'application/json')

        new_coupon = Product.objects.get(id=self.coupon.id)
        coupon_category = ProductCategory.objects.get(product=new_coupon)
        self.assertEqual(category.id, coupon_category.category.id)

    def test_update_client(self):
        path = reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id})
        client = 'Člient 123'
        data = {
            'id': self.coupon.id,
            'client': client
        }
        self.client.put(path, json.dumps(data), 'application/json')

        new_coupon = Product.objects.get(id=self.coupon.id)
        basket = Basket.objects.filter(lines__product_id=new_coupon.id).first()
        invoice = Invoice.objects.get(order__basket=basket)
        self.assertEqual(invoice.business_client.name, client)

    def test_update_coupon_price(self):
        """Test that updating the price updates all of it's stock record prices."""
        path = reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id})
        data = {
            'id': self.coupon.id,
            'price': 77
        }
        self.client.put(path, json.dumps(data), 'application/json')

        new_coupon = Product.objects.get(id=self.coupon.id)
        stock_records = StockRecord.objects.filter(product=new_coupon).all()
        for stock_record in stock_records:
            self.assertEqual(stock_record.price_excl_tax, 77)

    def test_update_note(self):
        path = reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id})
        note = 'Thiš iš the tešt note.'
        data = {
            'id': self.coupon.id,
            'note': note
        }
        self.client.put(path, json.dumps(data), 'application/json')

        new_coupon = Product.objects.get(id=self.coupon.id)
        self.assertEqual(new_coupon.attr.note, note)

    def test_update_dynamic_range_values(self):
        """ Verify dynamic range values are updated in case range has no catalog. """
        voucher_range = self.coupon.attr.coupon_vouchers.vouchers.first().offers.first().benefit.range
        Range.objects.filter(id=voucher_range.id).update(**{'catalog': None})
        voucher_range, data = self._get_voucher_range_with_updated_dynamic_catalog_values()
        self.assertEqual(voucher_range.catalog_query, data['catalog_query'])
        self.assertEqual(voucher_range.course_seat_types, data['course_seat_types'][0])

    def test_update_catalog_type(self):
        """Test updating dynamic range values deletes catalog."""
        voucher_range, data = self._get_voucher_range_with_updated_dynamic_catalog_values()
        self.assertEqual(voucher_range.catalog, None)
        self.assertEqual(voucher_range.catalog_query, data['catalog_query'])
        self.assertEqual(voucher_range.course_seat_types, data['course_seat_types'][0])

    def test_update_coupon_benefit_value(self):
        vouchers = self.coupon.attr.coupon_vouchers.vouchers.all()
        max_uses = vouchers[0].offers.first().max_global_applications
        benefit_value = Decimal(54)

        CouponViewSet().update_coupon_benefit_value(
            benefit_value=benefit_value,
            vouchers=vouchers,
            coupon=self.coupon
        )
        for voucher in vouchers:
            self.assertEqual(voucher.offers.first().benefit.value, benefit_value)
            self.assertEqual(voucher.offers.first().max_global_applications, max_uses)

    def test_update_coupon_client(self):
        baskets = Basket.objects.filter(lines__product_id=self.coupon.id)
        basket = baskets.first()
        client_username = 'Tešt Člient Ušername'
        CouponViewSet().update_coupon_client(
            baskets=baskets,
            client_username=client_username
        )

        invoice = Invoice.objects.get(order__basket=basket)
        self.assertEqual(invoice.business_client.name, client_username)

    def test_update_invoice_data(self):
        invoice = Invoice.objects.get(order__lines__product=self.coupon)
        self.assertEqual(invoice.discount_type, Invoice.PERCENTAGE)
        CouponViewSet().update_invoice_data(
            coupon=self.coupon,
            data={
                'invoice_discount_type': Invoice.FIXED
            }
        )

        invoice = Invoice.objects.get(order__lines__product=self.coupon)
        self.assertEqual(invoice.discount_type, Invoice.FIXED)

    @ddt.data('audit', 'honor')
    def test_restricted_course_mode(self, mode):
        """Test that an exception is raised when a black-listed course mode is used."""
        course = CourseFactory(id='black/list/mode')
        seat = course.create_or_update_seat(mode, False, 0, self.partner)
        # Seats derived from a migrated "audit" mode do not have a certificate_type attribute.
        if mode == 'audit':
            seat = ProductFactory()
        self.data.update({'stock_record_ids': [StockRecord.objects.get(product=seat).id]})
        response = self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_dynamic_catalog_coupon(self):
        """ Verify dynamic range values are returned. """
        catalog_query = 'key:*'
        course_seat_types = ['verified']
        self.data.update({
            'title': 'Đynamič ćoupon',
            'catalog_query': catalog_query,
            'course_seat_types': course_seat_types,
        })
        self.data.pop('stock_record_ids')
        course, __ = self.create_course_and_seat(course_id='dynamic/catalog/coupon')
        self.mock_dynamic_catalog_course_runs_api(query=catalog_query, course_run=course)

        response = self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        coupon_id = json.loads(response.content)['coupon_id']
        details_response = self.client.get(reverse('api:v2:coupons-detail', args=[coupon_id]))
        detail = json.loads(details_response.content)
        self.assertEqual(detail['catalog_query'], catalog_query)
        self.assertEqual(detail['course_seat_types'], course_seat_types)

    @ddt.data(
        (Voucher.SINGLE_USE, None),
        (Voucher.ONCE_PER_CUSTOMER, 2),
        (Voucher.MULTI_USE, 2)
    )
    @ddt.unpack
    def test_multi_use_single_use_coupon(self, voucher_type, max_uses):
        """Test that a SINGLE_USE coupon has the default max_uses value and other the set one. """
        self.data.update({
            'max_uses': max_uses,
            'voucher_type': voucher_type,
        })
        response_data = self.get_response_json('POST', COUPONS_LINK, data=self.data)
        coupon = Product.objects.get(id=response_data['coupon_id'])
        voucher = coupon.attr.coupon_vouchers.vouchers.first()
        self.assertEquals(voucher.offers.first().max_global_applications, max_uses)

    def update_prepaid_invoice_data(self):
        """ Update the 'data' class variable with invoice information. """
        invoice_data = {
            'invoice_type': Invoice.PREPAID,
            'invoice_number': 'INVOIĆE-00001',
            'invoice_payment_date': datetime.datetime(2015, 1, 1, tzinfo=pytz.UTC).isoformat(),
            'invoice_discount_type': None,
            'invoice_discount_value': 77
        }
        self.data.update(invoice_data)

    def assert_invoice_serialized_data(self, coupon_data):
        """ Assert that the coupon details show the invoice data. """
        invoice_details = coupon_data['payment_information']['Invoice']
        self.assertEqual(invoice_details['type'], self.data['invoice_type'])
        self.assertEqual(invoice_details['number'], self.data['invoice_number'])
        self.assertEqual(invoice_details['discount_type'], self.data['invoice_discount_type'])
        self.assertEqual(invoice_details['discount_value'], self.data['invoice_discount_value'])

    def test_coupon_with_invoice_data(self):
        """ Verify an invoice is created with the proper data. """
        self.update_prepaid_invoice_data()
        response = self.get_response_json('POST', COUPONS_LINK, data=self.data)
        invoice = Invoice.objects.get(order__lines__product__id=response['coupon_id'])
        self.assertEqual(invoice.type, self.data['invoice_type'])
        self.assertEqual(invoice.number, self.data['invoice_number'])
        self.assertEqual(invoice.payment_date.isoformat(), self.data['invoice_payment_date'])
        details = self.get_response_json('GET', reverse('api:v2:coupons-detail', args=[response['coupon_id']]))
        self.assert_invoice_serialized_data(details)

    def test_coupon_invoice_update(self):
        """ Verify a coupon is updated with new invoice data. """
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

    def create_coupon_with_email_domains(self, email_domains):
        """ Helper function to create a new coupon with email domains set.

        Args:
            email_domains: comma-separated list of email domains.

        Returns:
            JSON of the coupon details.
        """
        self.data.update({'email_domains': email_domains})

        response = self.client.post(COUPONS_LINK, json.dumps(self.data), 'application/json')
        coupon_id = json.loads(response.content)['coupon_id']

        details_response = self.client.get(reverse('api:v2:coupons-detail', args=[coupon_id]))
        return json.loads(details_response.content)

    def test_coupon_with_email_domains(self):
        """ Verify a coupon is created with specified email domains. """
        email_domains = 'example.com'
        details = self.create_coupon_with_email_domains(email_domains)
        self.assertEqual(details['email_domains'], email_domains)

    def test_update_email_domains(self):
        """ Verify a coupons email domains is updated. """
        path = reverse('api:v2:coupons-detail', args=[self.coupon.id])
        details = self.get_response_json('GET', path)
        self.assertIsNone(details['email_domains'])

        email_domains = 'example.com'
        self.data.update({'email_domains': email_domains})

        response = self.get_response_json('PUT', path, self.data)
        self.assertEqual(response['email_domains'], email_domains)

    def test_not_update_email_domains(self):
        """ Verify the email domains are not deleted when updated. """
        email_domains = 'example.com'
        details = self.create_coupon_with_email_domains(email_domains)
        offer = Product.objects.get(id=details['id']).attr.coupon_vouchers.vouchers.first().offers.first()
        self.assertEqual(details['email_domains'], email_domains)
        self.assertEqual(offer.email_domains, email_domains)

        self.data.pop('email_domains', None)
        path = reverse('api:v2:coupons-detail', args=[details['id']])
        self.get_response_json('PUT', path, self.data)
        self.assertEqual(offer.email_domains, email_domains)

    def test_update_max_uses_field(self):
        """Verify max_uses field can be updated."""
        path = reverse('api:v2:coupons-detail', args=[self.coupon.id])
        details = self.get_response_json('GET', path)
        self.assertIsNone(details['max_uses'])

        max_uses = 3
        self.data.update({'max_uses': max_uses})
        response = self.get_response_json('PUT', path, self.data)
        self.assertEqual(response['max_uses'], max_uses)


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
