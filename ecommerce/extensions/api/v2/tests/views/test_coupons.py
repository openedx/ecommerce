# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

import ddt
from django.core.urlresolvers import reverse
from django.db.utils import IntegrityError
from django.test import RequestFactory
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_class, get_model
from rest_framework import status

from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api.constants import APIConstants as AC
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.tests.factories import ProductFactory, SiteConfigurationFactory, SiteFactory
from ecommerce.tests.mixins import CouponMixin, ThrottlingMixin
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


class CouponViewSetTest(CouponMixin, CourseCatalogTestMixin, TestCase):
    """Unit tests for creating coupon order."""

    def setUp(self):
        super(CouponViewSetTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        course = CourseFactory(id='edx/Demo_Course/DemoX')
        course.create_or_update_seat('verified', True, 50, self.partner)

        self.catalog = Catalog.objects.create(partner=self.partner)
        self.product_class, __ = ProductClass.objects.get_or_create(name='Coupon')
        self.coupon_data = {
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
        }

    def setup_site_configuration(self):
        site_configuration = SiteConfigurationFactory(partner__name='TestX')
        site = SiteFactory()
        site.siteconfiguration = site_configuration
        return site

    def test_create(self):
        """Test the create method."""
        self.coupon_data.update({
            'title': 'Test coupon',
            'client_username': 'Client',
            'stock_record_ids': [1],
            'voucher_type': Voucher.SINGLE_USE,
            'price': 100,
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
        self.assertEqual(category, self.category)

    def test_append_to_existing_coupon(self):
        """Test adding additional vouchers to an existing coupon."""
        self.create_coupon(partner=self.partner, catalog=self.catalog)
        coupon_append = CouponViewSet().create_coupon_product(
            title='Test coupon',
            price=100,
            data=self.coupon_data
        )

        self.assertEqual(Product.objects.filter(product_class=self.product_class).count(), 1)
        self.assertEqual(StockRecord.objects.filter(product=coupon_append).count(), 1)
        self.assertEqual(coupon_append.attr.coupon_vouchers.vouchers.count(), 7)
        self.assertEqual(coupon_append.attr.coupon_vouchers.vouchers.filter(usage=Voucher.ONCE_PER_CUSTOMER).count(), 2)

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

    def test_delete_coupon(self):
        """Test the coupon deletion."""
        coupon = self.create_coupon(partner=self.partner)
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
        self.create_course_and_seat('edx/Demo_Course1/DemoX', 50)
        self.create_course_and_seat('edx/Demo_Course2/DemoX', 100)
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
            AC.KEYS.START_DATE: '2030-01-01',
            AC.KEYS.END_DATE: '2035-01-01'
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
