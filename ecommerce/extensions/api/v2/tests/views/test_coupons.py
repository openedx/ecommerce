# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

import ddt
from django.core.urlresolvers import reverse
from django.db.utils import IntegrityError
from django.test import RequestFactory
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_model
from rest_framework import status

from ecommerce.coupons import api as coupons_api
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.tests.factories import ProductFactory, SiteConfigurationFactory, SiteFactory
from ecommerce.tests.mixins import CouponMixin, ThrottlingMixin
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


class CouponViewSetTest(CouponMixin, CourseCatalogTestMixin, TestCase):
    """Unit tests for creating coupon order."""

    def setUp(self):
        super(CouponViewSetTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        course = CourseFactory(id='edx/Demo_Course/DemoX')
        verified_seat = course.create_or_update_seat('verified', True, 50, self.partner)
        stock_record = StockRecord.objects.filter(product=verified_seat).first()

        self.catalog = Catalog.objects.create(partner=self.partner)
        self.catalog.stock_records.add(stock_record)
        self.stock_record_ids = [stock_record.id for stock_record in self.catalog.stock_records.all()]

        self.product_class, __ = ProductClass.objects.get_or_create(name='Coupon')
        self.coupon_data = {
            'title': "Test CouponViewSet Coupon",
            'price': 100,
            'stock_record_ids': self.stock_record_ids,
            'partner': self.partner,
            'categories': [self.category],
            'note': None,
            'create_vouchers': True,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'start_date': '2015-1-1',
            'end_date': '2020-1-1',
            'code': None,
            'quantity': 1,
            'voucher_type': Voucher.ONCE_PER_CUSTOMER,
            'course_key': course.id,
            'client_username': 'Client',
            'catalog_name': 'CouponViewSet Catalog Name'
        }

    def _create_or_update_test_coupon_product(self, coupon_data):
        """
        Generate a new coupon product for use by tests
        """
        return coupons_api.create_or_update_coupon_product(
            title=coupon_data['title'],
            price=coupon_data['price'],
            stock_record_ids=coupon_data['stock_record_ids'],
            partner=coupon_data['partner'],
            categories=coupon_data['categories'],
            note=coupon_data['note'],
            create_vouchers=coupon_data['create_vouchers'],
            benefit_type=coupon_data['benefit_type'],
            benefit_value=coupon_data['benefit_value'],
            start_date=coupon_data['start_date'],
            end_date=coupon_data['end_date'],
            code=coupon_data['code'],
            quantity=coupon_data['quantity'],
            voucher_type=coupon_data['voucher_type'],
            course_key=coupon_data['course_key'],
            catalog_name=coupon_data['catalog_name']
        )

    def setup_site_configuration(self):
        site_configuration = SiteConfigurationFactory(partner__name='TestX')
        site = SiteFactory()
        site.siteconfiguration = site_configuration
        return site

    def test_create(self):
        """Test the create method."""
        self.coupon_data.update({
            'title': 'Test CouponViewSet.create Coupon',
            'stock_record_ids': [1],
            'voucher_type': Voucher.SINGLE_USE,
            'category_ids': [self.category.id]
        })
        request = RequestFactory()
        request.user = self.user
        request.data = self.coupon_data
        request.site = self.site

        response = CouponViewSet().create(request)

        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(
            response.data,
            {'payment_data': {'payment_processor_name': 'Invoice'}, 'id': 1, 'order': 1, 'coupon_id': 3}
        )

    def test_append_vouchers_to_existing_coupon_product(self):
        """Test adding additional vouchers to an existing coupon product."""
        coupon_title = 'Existing Coupon'
        coupon_catalog_name = 'Existing Catalog'
        self.create_coupon(
            title=coupon_title,
            catalog_name=coupon_catalog_name,
            stock_record_ids=[1]
        )
        self.coupon_data.update({
            'title': coupon_title,
            'catalog_name': coupon_catalog_name,
            'stock_record_ids': [1],
            'quantity': 2
        })
        appended_coupon = self._create_or_update_test_coupon_product(self.coupon_data)
        self.assertEqual(Product.objects.filter(product_class=self.product_class).count(), 1)
        self.assertEqual(StockRecord.objects.filter(product=appended_coupon).count(), 1)
        self.assertEqual(appended_coupon.attr.coupon_vouchers.vouchers.count(), 7)
        self.assertEqual(
            appended_coupon.attr.coupon_vouchers.vouchers.filter(usage=Voucher.ONCE_PER_CUSTOMER).count(), 2
        )

    def test_custom_voucher_code(self):
        """Test creating a coupon with custom voucher code."""
        self.coupon_data.update({
            'title': 'Custom Code Coupon',
            'voucher_type': Voucher.ONCE_PER_CUSTOMER,
            'code': 'CUSTOMCODE'
        })
        custom_coupon = self._create_or_update_test_coupon_product(self.coupon_data)
        self.assertEqual(custom_coupon.attr.coupon_vouchers.vouchers.count(), 1)
        self.assertEqual(custom_coupon.attr.coupon_vouchers.vouchers.first().code, 'CUSTOMCODE')

    def test_custom_voucher_code_integrity_error(self):
        """Test custom coupon code duplication."""
        self.coupon_data.update({
            'title': 'Custom Code Coupon',
            'code': 'CUSTOMCODE'
        })
        self._create_or_update_test_coupon_product(self.coupon_data)

        with self.assertRaises(IntegrityError):
            self.coupon_data.update({
                'title': 'Coupon with integrity issue'
            })
            self._create_or_update_test_coupon_product(self.coupon_data)

    def test_coupon_note(self):
        """Test creating a coupon with a note."""
        coupon_title = 'Coupon with Note'
        coupon_note = '𝑵𝑶𝑻𝑬'
        self.coupon_data.update({
            'title': coupon_title,
            'note': coupon_note
        })
        note_coupon = self._create_or_update_test_coupon_product(self.coupon_data)

        self.assertEqual(note_coupon.attr.note, coupon_note)
        self.assertEqual(note_coupon.title, coupon_title)

    def test_add_product_to_basket(self):
        """Test adding a coupon product to a basket."""
        self.create_coupon()

        self.assertIsInstance(self.basket, Basket)
        self.assertEqual(Basket.objects.count(), 1)
        self.assertEqual(self.basket.lines.count(), 1)
        self.assertEqual(self.basket.lines.first().price_excl_tax, 100)

    def test_create_order(self):
        """Test the order creation."""
        self.create_coupon()

        self.assertEqual(self.response_data[AC.KEYS.BASKET_ID], 1)
        self.assertEqual(self.response_data[AC.KEYS.ORDER], 1)
        self.assertEqual(self.response_data[AC.KEYS.PAYMENT_DATA][AC.KEYS.PAYMENT_PROCESSOR_NAME], 'Invoice')

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.first().status, 'Complete')
        self.assertEqual(Order.objects.first().total_incl_tax, 100)
        self.assertEqual(Basket.objects.first().status, 'Submitted')

    def test_delete_coupon(self):
        """Test the coupon deletion."""
        coupon = self.create_coupon()
        self.assertEqual(Product.objects.filter(product_class=self.product_class).count(), 1)
        self.assertEqual(StockRecord.objects.filter(product=coupon).count(), 1)
        coupon_voucher_qs = CouponVouchers.objects.filter(coupon=coupon)
        self.assertEqual(coupon_voucher_qs.count(), 1)
        self.assertEqual(coupon_voucher_qs.first().vouchers.count(), 5)

        request = RequestFactory()
        request.site = self.setup_site_configuration()
        response = CouponViewSet().destroy(request, coupon.id)

        self.assertEqual(Product.objects.filter(product_class=self.product_class).count(), 0)
        self.assertEqual(StockRecord.objects.filter(product=coupon).count(), 0)
        coupon_voucher_qs = CouponVouchers.objects.filter(coupon=coupon)
        self.assertEqual(coupon_voucher_qs.count(), 0)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(response.status_code, 204)

        response = CouponViewSet().destroy(request, 100)
        self.assertEqual(response.status_code, 404)


@ddt.ddt
class CouponViewSetFunctionalTest(CouponMixin, CourseCatalogTestMixin, ThrottlingMixin, TestCase):
    """Test the coupon order creation functionality."""

    def setUp(self):
        super(CouponViewSetFunctionalTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        self.course_key_1 = 'edX/Demo_Course1/DemoX'
        self.course_key_2 = 'edX/Demo_Course2/DemoX'
        self.create_course_and_seat(self.course_key_1, 50)
        self.create_course_and_seat(self.course_key_2, 100)
        self.data = {
            'title': 'Test CouponMixin Coupon',
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

    def create_course_and_seat(self, course_id, price):
        """Create a course and a seat product for that course."""
        course = CourseFactory(id=course_id)
        course.create_or_update_seat('verified', True, price, self.partner)

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
        self.assertEqual(Order.objects.first().lines.first().product.title, 'Test CouponMixin Coupon')

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
        response_data = json.loads(response.content)['results']

        # For each coupon returned...
        for coupon_data in response_data:
            self.assertEqual(coupon_data['title'], 'Test CouponMixin Coupon')
            self.assertEqual(coupon_data['coupon_type'], 'Enrollment code')
            self.assertEqual(coupon_data['client'], self.user.username)
            self.assertEqual(coupon_data['price'], '100.00')
            self.assertIsNotNone(coupon_data['last_edited'][0])

            self.assertEqual(len(coupon_data['seats']), 1)
            self.assertEqual(len(coupon_data['vouchers']), 2)
            self.assertEqual(len(coupon_data['categories']), 2)

            # For each seat in the coupon data...
            for seat_data in coupon_data['seats']:

                # For each attribute in the seat data...
                for attribute in seat_data['attribute_values']:
                    if attribute['name'] == 'course_key':
                        self.assertEqual(attribute['value'], self.course_key_2)
                    if attribute['name'] == 'certificate_type':
                        self.assertEqual(attribute['value'], 'verified')

            # For each voucher in the coupon data...
            for voucher_data in coupon_data['vouchers']:
                self.assertEqual(voucher_data['benefit'][1], 100.0)
                self.assertIsNotNone(voucher_data['redeem_url'])
                self.assertEqual(voucher_data['start_datetime'], '2015-01-01T05:00:00Z')
                self.assertEqual(voucher_data['end_datetime'], '2020-01-01T05:00:00Z')
                self.assertIsNotNone(voucher_data['code'])
                self.assertTrue(voucher_data['is_available_to_user'][0])

    def test_list_coupon_note(self):
        """Test note is returned for coupon with note."""
        self.data.update({
            'note': 'Coupon note',
        })
        self.client.post(COUPONS_LINK, data=self.data, format='json')
        response = self.client.get(COUPONS_LINK)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['results'][0]['note'], 'Coupon note')

    def test_list_discount_coupons(self):
        """Test discount code values are returned for discount coupon."""
        self.data['title'] = 'Test discount code'
        self.data['benefit_value'] = 20
        self.client.post(COUPONS_LINK, data=self.data, format='json')
        response = self.client.get(COUPONS_LINK)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['results'][0]['coupon_type'], 'Discount code')
        self.assertEqual(response_data['results'][0]['vouchers'][0]['benefit'][1], 20.0)

    def test_update(self):
        """Test updating a coupon."""
        coupon = Product.objects.get(title='Test CouponMixin Coupon')
        path = reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id})
        response = self.client.put(path, json.dumps({'title': 'New title'}), 'application/json')
        response_data = json.loads(response.content)
        self.assertEqual(response_data['id'], coupon.id)
        self.assertEqual(response_data['title'], 'New title')

    def test_update_datetimes(self):
        """Test that updating a coupons date updates all of it's voucher dates."""
        coupon = Product.objects.get(title='Test CouponMixin Coupon')
        voucher_code = coupon.attr.coupon_vouchers.vouchers.first().code
        path = reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id})
        data = {
            'id': coupon.id,
            AC.KEYS.START_DATE: '2030-01-01',
            AC.KEYS.END_DATE: '2035-01-01'
        }
        response = self.client.put(path, json.dumps(data), 'application/json')
        response_data = json.loads(response.content)
        self.assertEqual(response_data['id'], coupon.id)
        self.assertEqual(response_data['title'], 'Test CouponMixin Coupon')

        new_coupon = Product.objects.get(id=coupon.id)
        self.assertEqual(new_coupon.attr.coupon_vouchers.vouchers.first().code, voucher_code)
        self.assertEqual(new_coupon.attr.coupon_vouchers.vouchers.first().start_datetime.year, 2030)
        self.assertEqual(new_coupon.attr.coupon_vouchers.vouchers.last().start_datetime.year, 2030)
        self.assertEqual(new_coupon.attr.coupon_vouchers.vouchers.first().end_datetime.year, 2035)
        self.assertEqual(new_coupon.attr.coupon_vouchers.vouchers.last().end_datetime.year, 2035)

    def test_exception_for_multi_use_voucher_type(self):
        """Test that an exception is raised for multi-use voucher types."""
        self.data.update({
            'voucher_type': Voucher.MULTI_USE,
        })

        with self.assertRaises(NotImplementedError):
            self.client.post(COUPONS_LINK, data=self.data, format='json')

    @ddt.data('audit', 'honor')
    def test_restricted_course_mode(self, mode):
        """Test that an exception is raised when a black-listed course mode is used."""
        course = CourseFactory(id='black/list/mode')
        seat = course.create_or_update_seat(mode, False, 0, self.partner)
        # Seats derived from a migrated "audit" mode do not have a certificate_type attribute.
        if mode == 'audit':
            seat = ProductFactory()
        self.data.update({'stock_record_ids': [StockRecord.objects.get(product=seat).id], })
        with self.assertRaises(Exception):
            response = self.client.post(COUPONS_LINK, data=self.data, format='json')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


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
