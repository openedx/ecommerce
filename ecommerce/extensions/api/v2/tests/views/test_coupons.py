# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from decimal import Decimal
import json

import ddt
import httpretty
from django.core.urlresolvers import reverse
from django.test import RequestFactory
from oscar.apps.catalogue.categories import create_from_breadcrumbs
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from rest_framework import status

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.coupons.tests.mixins import CouponMixin, CourseCatalogMockMixin
from ecommerce.extensions.api.v2.views.coupons import CouponViewSet
from ecommerce.extensions.api.v2.tests.views.mixins import CatalogMixin
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.invoice.models import Invoice
from ecommerce.tests.mixins import APIMixin, ThrottlingMixin
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
class CouponViewSetTest(CatalogMixin, CouponMixin, TestCase):
    """Tests for Coupon API endpoints."""
    def setUp(self):
        super(CouponViewSetTest, self).setUp()
        self.catalog = Catalog.objects.create(partner=self.partner)
        self.coupon_data.update({'catalog': self.catalog, 'partner': self.partner})

    @ddt.data(
        (Voucher.ONCE_PER_CUSTOMER, 2, 2),
        (Voucher.SINGLE_USE, 2, None)
    )
    @ddt.unpack
    def test_create(self, voucher_type, max_uses, expected_max_uses):
        """Test the create API endpoint."""
        self.coupon_data.update({'max_uses': max_uses, 'voucher_type': voucher_type})
        request = RequestFactory()
        request.user = self.user
        request.data = self.coupon_data
        request.site = self.site
        request.COOKIES = {}

        response = CouponViewSet().create(request)

        coupon = Product.objects.get(title=self.coupon_data['title'])
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertDictEqual(response.data, {'id': coupon.id})
        self.assertEqual(
            coupon.attr.coupon_vouchers.vouchers.first().offers.first().max_global_applications,
            expected_max_uses
        )

    def test_create_coupon_product(self):
        """Test the created coupon data."""
        self.create_coupon()

        self.assertEqual(Product.objects.filter(product_class=self.coupon_product_class).count(), 1)
        self.assertIsInstance(self.coupon, Product)
        self.assertEqual(self.coupon.title, 'Test coupon')
        self.assertEqual(StockRecord.objects.filter(product=self.coupon).count(), 1)
        self.assertEqual(self.coupon.attr.coupon_vouchers.vouchers.count(), 1)

        stock_record = StockRecord.objects.get(product=self.coupon)
        self.assertEqual(stock_record.price_currency, 'USD')
        self.assertEqual(stock_record.price_excl_tax, 100)

        category = ProductCategory.objects.get(product=self.coupon).category
        self.assertEqual(category, self.category)

    @ddt.data(
        (1, True, 2),
        (2, False, 2)
    )
    @ddt.unpack
    def test_creating_multi_offer_coupon(self, max_uses, offers_equal, quantity):
        """Test the creation of a multi-offer coupon."""
        self.create_coupon(max_uses=max_uses, quantity=quantity)
        coupon_vouchers = self.coupon.attr.coupon_vouchers.vouchers.all()
        first_offer = coupon_vouchers[0].offers.first()
        second_offer = coupon_vouchers[1].offers.first()

        self.assertEqual(first_offer.max_global_applications, max_uses)
        self.assertEqual(first_offer.max_global_applications, second_offer.max_global_applications)
        if offers_equal:
            self.assertEqual(first_offer, second_offer)
        else:
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

        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.first().status, 'Complete')
        self.assertEqual(Order.objects.first().total_incl_tax, 100)
        self.assertEqual(Basket.objects.first().status, 'Submitted')

    def test_create_update_data_dict(self):
        """Test creating update data dictionary"""
        fields = ['end_datetime', 'start_datetime', 'title']
        data = CouponViewSet().create_update_data_dict(
            data=self.coupon_data,
            fields=fields
        )

        self.assertDictEqual(
            data,
            {
                'end_datetime': self.coupon_data['end_datetime'],
                'start_datetime': self.coupon_data['start_datetime'],
                'title': self.coupon_data['title'],
            })

    def test_delete_coupon(self):
        """Test the coupon deletion."""
        self.create_coupon(partner=self.partner)

        self.assertEqual(Product.objects.filter(product_class=self.coupon_product_class).count(), 1)
        self.assertEqual(StockRecord.objects.filter(product=self.coupon).count(), 1)

        coupon_voucher_qs = CouponVouchers.objects.filter(coupon=self.coupon)
        self.assertEqual(coupon_voucher_qs.count(), 1)
        self.assertEqual(coupon_voucher_qs.first().vouchers.count(), 1)

        request = RequestFactory()
        response = CouponViewSet().destroy(request, self.coupon.id)

        self.assertEqual(Product.objects.filter(product_class=self.coupon_product_class).count(), 0)
        self.assertEqual(StockRecord.objects.filter(product=self.coupon).count(), 0)

        coupon_voucher_qs = CouponVouchers.objects.filter(coupon=self.coupon)
        self.assertEqual(coupon_voucher_qs.count(), 0)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = CouponViewSet().destroy(request, 100)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


@ddt.ddt
class CouponViewSetFunctionalTest(APIMixin, CouponMixin, CourseCatalogMockMixin, ThrottlingMixin, TestCase):
    """Test the coupon order creation functionality."""

    def setUp(self):
        super(CouponViewSetFunctionalTest, self).setUp()
        self.create_and_login_user()

        self.response_data, self.status_code = self.get_response_json(
            data=self.coupon_data,
            method='POST',
            path=COUPONS_LINK
        )
        self.coupon = Product.objects.get(title=self.coupon_data['title'])

    def get_coupon_details(self, coupon_id):
        """Utility method that performs the call to the Coupon retrieve API endpoint."""
        return self.get_response_json(
            method='GET',
            path=reverse('api:v2:coupons-detail', args=[coupon_id]),
        )

    def get_coupon_list(self):
        """Utility method that performs the call to the Coupon list API endpoint."""
        return self.get_response_json(method='GET', path=COUPONS_LINK)

    def create_coupon_product(self, data):
        """Utility method that performs the call to the Coupon create API endpoint."""
        return self.get_response_json(
            data=data,
            method='POST',
            path=COUPONS_LINK
        )

    def update_coupon(self, coupon_id, data):
        """Utility method that performs the call to the Coupon update API endpoint."""
        return self.get_response_json(
            data=data,
            method='PUT',
            path=reverse('api:v2:coupons-detail', kwargs={'pk': coupon_id}),
        )

    def test_create_serializer_data(self):
        """Test if coupon serializer creates data for details page"""
        details_response, __ = self.get_response_json(
            'GET',
            reverse('api:v2:coupons-detail', args=[self.coupon.id]),
            data=self.coupon_data
        )
        self.assertEqual(details_response['coupon_type'], 'Enrollment code')
        self.assertEqual(details_response['code_status'], 'ACTIVE')

    def test_response(self):
        """Test the response data given after the order was created."""
        self.assertEqual(self.status_code, status.HTTP_201_CREATED)
        self.assertDictEqual(self.response_data, {'id': self.coupon.id})

    def test_order(self):
        """Test the order data after order creation."""
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.first().status, 'Complete')
        self.assertEqual(Order.objects.first().lines.count(), 1)
        self.assertEqual(Order.objects.first().lines.first().product, self.coupon)

    @ddt.data(status.HTTP_201_CREATED, status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
    def test_authentication_required(self, expected_status_code):
        """Test that a guest cannot access the view."""
        if expected_status_code == status.HTTP_401_UNAUTHORIZED:
            self.client.logout()
        elif expected_status_code == status.HTTP_403_FORBIDDEN:
            self.create_and_login_user(is_staff=False)
        __, status_code = self.create_coupon_product(data=self.coupon_data)

        self.assertEqual(status_code, expected_status_code)

    def test_list_coupons(self):
        """Test that the endpoint returns information needed for the details page."""
        response_data, status_code = self.get_coupon_list()
        coupon_data = response_data['results'][0]

        self.assertEqual(status_code, status.HTTP_200_OK)
        self.assertTrue('id' in coupon_data)
        self.assertEqual(coupon_data['title'], self.coupon_data['title'])

    def test_already_existing_code(self):
        """Test custom coupon code duplication."""
        self.coupon_data.update({'code': 'CUSTOMCODE', 'quantity': 1})
        for __ in range(2):
            ___, status_code = self.create_coupon_product(data=self.coupon_data)

        self.assertEqual(status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_coupon(self):
        """Test updating a coupon."""
        new_category = factories.CategoryFactory()
        new_note = 'Thiš iš a new tešt note.'
        new_title = 'New title'
        response_data, __ = self.update_coupon(coupon_id=self.coupon.id, data={
            'category': new_category.name,
            'note': new_note,
            'title': new_title
        })

        self.assertEqual(response_data['id'], self.coupon.id)
        self.assertEqual(response_data['title'], new_title)

        new_coupon = Product.objects.get(id=self.coupon.id)
        coupon_category = ProductCategory.objects.get(product=new_coupon)

        self.assertEqual(new_coupon.title, new_title)
        self.assertEqual(new_category.id, coupon_category.category.id)
        self.assertEqual(new_coupon.attr.note, new_note)

    def test_update_vouchers(self):
        """Test updating vouchers associated with the coupon."""
        new_title = 'New title'
        vouchers = self.coupon.attr.coupon_vouchers.vouchers.all()
        max_uses = vouchers[0].offers.first().max_global_applications
        response_data, __ = self.update_coupon(
            coupon_id=self.coupon.id,
            data={
                'benefit_value': 50,
                'end_datetime': '2035-01-01',
                'name': new_title,
                'start_datetime': '2030-01-01',
            }
        )

        self.assertEqual(response_data['id'], self.coupon.id)

        new_coupon = Product.objects.get(id=self.coupon.id)
        vouchers = new_coupon.attr.coupon_vouchers.vouchers.all()
        for voucher in vouchers:
            self.assertEqual(voucher.name, new_title)
            self.assertEqual(voucher.start_datetime.year, 2030)
            self.assertEqual(voucher.end_datetime.year, 2035)
            self.assertEqual(voucher.offers.first().benefit.value, Decimal(50.0))
            self.assertEqual(voucher.offers.first().max_global_applications, max_uses)

    def test_update_baskets(self):
        """Test updating basket orders associated with the coupon."""
        new_client = 'New Člient 123'
        self.update_coupon(
            coupon_id=self.coupon.id,
            data={'client': new_client}
        )

        new_coupon = Product.objects.get(id=self.coupon.id)
        baskets = Basket.objects.filter(lines__product_id=new_coupon.id).all()
        for basket in baskets:
            invoice = Invoice.objects.get(order__basket=basket)
            self.assertEqual(invoice.business_client.name, new_client)

    def test_update_stock_records(self):
        """Test updating stock records associated with the coupon."""
        new_price = 77
        self.update_coupon(
            coupon_id=self.coupon.id,
            data={'price': new_price}
        )

        new_coupon = Product.objects.get(id=self.coupon.id)
        stock_records = StockRecord.objects.filter(product=new_coupon).all()
        for stock_record in stock_records:
            self.assertEqual(stock_record.price_excl_tax, new_price)

    def test_update_invoice_data(self):
        invoice = Invoice.objects.get(order__basket__lines__product=self.coupon)
        self.assertEqual(invoice.discount_type, Invoice.PERCENTAGE)

        self.update_coupon(
            coupon_id=self.coupon.id,
            data={'invoice_discount_type': Invoice.FIXED}
        )

        invoice = Invoice.objects.get(order__basket__lines__product=self.coupon)
        self.assertEqual(invoice.discount_type, Invoice.FIXED)

    @ddt.data('audit', 'honor')
    def test_restricted_course_mode(self, mode):
        """Test that an exception is raised when a black-listed course mode is used."""
        __, seat = self.create_course_and_seat(
            id_verification=False,
            partner=self.partner,
            seat_type=mode,
        )
        self.coupon_data.update({'stock_record_ids': [StockRecord.objects.get(product=seat).id]})
        self.update_coupon(
            coupon_id=self.coupon.id,
            data={'invoice_discount_type': Invoice.FIXED}
        )
        __, status_code = self.create_coupon_product(data=self.coupon_data)
        self.assertEqual(status_code, status.HTTP_400_BAD_REQUEST)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_dynamic_catalog_coupon(self):
        """ Verify dynamic range values are returned. """
        catalog_query = 'key:*'
        course_seat_types = ['verified']
        self.coupon_data.update({
            'catalog_query': catalog_query,
            'course_seat_types': course_seat_types,
            'title': 'Đynamič ćoupon',
        })
        self.coupon_data.pop('stock_record_ids')
        course, seat = self.create_course_and_seat()
        self.mock_dynamic_catalog_course_runs_api(query=catalog_query, course_run=course)
        response_data, __ = self.create_coupon_product(data=self.coupon_data)
        response_data, __ = self.get_coupon_details(coupon_id=response_data['id'])

        self.assertEqual(response_data['catalog_query'], catalog_query)
        self.assertEqual(response_data['course_seat_types'], course_seat_types)
        self.assertEqual(response_data['seats'][0]['id'], seat.id)

    @ddt.data(
        (Voucher.SINGLE_USE, None),
        (Voucher.ONCE_PER_CUSTOMER, 2),
        (Voucher.MULTI_USE, 2)
    )
    @ddt.unpack
    def test_multi_use_single_use_coupon(self, voucher_type, max_uses):
        """Test that a SINGLE_USE coupon has the default max_uses value and other the set one. """
        self.coupon_data.update({
            'max_uses': max_uses,
            'voucher_type': voucher_type,
        })
        response_data, __ = self.create_coupon_product(data=self.coupon_data)
        coupon = Product.objects.get(id=response_data['id'])
        vouchers = coupon.attr.coupon_vouchers.vouchers.all()

        for voucher in vouchers:
            self.assertEquals(voucher.offers.first().max_global_applications, max_uses)

    def test_coupon_with_invoice_data(self):
        """ Verify an invoice is created with the proper data. """
        self.update_prepaid_invoice_data()
        response, __ = self.create_coupon_product(data=self.coupon_data)
        invoice = Invoice.objects.get(order__basket__lines__product__id=response['id'])

        self.assertEqual(invoice.type, self.coupon_data['invoice_type'])
        self.assertEqual(invoice.number, self.coupon_data['invoice_number'])
        self.assertEqual(invoice.payment_date.isoformat(), self.coupon_data['invoice_payment_date'])

        details, __ = self.get_coupon_details(coupon_id=response['id'])
        self.assert_invoice_serialized_data(details)

    def test_coupon_invoice_update(self):
        """ Verify a coupon is updated with new invoice data. """
        self.update_prepaid_invoice_data()
        response, __ = self.create_coupon_product(data=self.coupon_data)
        details, __ = self.get_coupon_details(coupon_id=response['id'])

        self.assert_invoice_serialized_data(details)

        self.coupon_data.update({
            'invoice_discount_type': Invoice.PERCENTAGE,
            'invoice_discount_value': 33,
            'invoice_payment_date': None,
            'invoice_number': None,
            'invoice_type': Invoice.POSTPAID,
        })
        updated_coupon, __ = self.update_coupon(coupon_id=response['id'], data=self.coupon_data)

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
