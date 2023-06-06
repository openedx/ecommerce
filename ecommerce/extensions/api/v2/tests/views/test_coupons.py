# -*- coding: utf-8 -*-


import datetime
import json
from decimal import Decimal
from uuid import uuid4

import ddt
import mock
import pytz
import responses
from django.test import RequestFactory
from django.urls import reverse
from django.utils.timezone import now
from oscar.core.loading import get_model
from oscar.test import factories
from rest_framework import status
from testfixtures import LogCapture

from ecommerce.coupons.tests.mixins import CouponMixin, DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.enterprise.conditions import AssignableEnterpriseCustomerCondition
from ecommerce.extensions.api.v2.views.coupons import DEPRECATED_COUPON_CATEGORIES, CouponViewSet, ValidationError
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.payment.models import EnterpriseContractMetadata
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.invoice.models import Invoice
from ecommerce.programs.constants import BENEFIT_MAP
from ecommerce.programs.custom import class_path
from ecommerce.tests.factories import PartnerFactory, ProductFactory, SiteConfigurationFactory
from ecommerce.tests.mixins import ThrottlingMixin
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Category = get_model('catalogue', 'Category')
Condition = get_model('offer', 'Condition')
Course = get_model('courses', 'Course')
Order = get_model('order', 'Order')
Product = get_model('catalogue', 'Product')
ProductCategory = get_model('catalogue', 'ProductCategory')
ProductClass = get_model('catalogue', 'ProductClass')
Range = get_model('offer', 'Range')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')

COUPONS_LINK = reverse('api:v2:coupons-list')
ENTERPRISE_COUPONS_LINK = reverse('api:v2:enterprise-coupons-list')
COUPON_CATEGORY_NAME = 'Coupons'
TEST_CATEGORIES = ['Financial Assistance', 'Partner No Rev - RAP', 'Geography Promotion', 'Marketing Partner Promotion',
                   'Upsell Promotion', 'edX Employee Request', 'Course Promotion', 'Partner No Rev - ORAP',
                   'Services-Other', 'Partner No Rev - Upon Redemption', 'Bulk Enrollment - Prepay', 'Support-Other',
                   'ConnectEd', 'Marketing-Other', 'Affiliate Promotion', 'Retention Promotion',
                   'Partner No Rev - Prepay', 'Paid Cohort', 'Bulk Enrollment - Integration', 'On-Campus Learners',
                   'Security Disclosure Reward', 'Other', 'Customer Service', 'Bulk Enrollment - Upon Redemption',
                   'B2B Affiliate Promotion', 'Scholarship']


class CouponViewSetTest(CouponMixin, DiscoveryTestMixin, TestCase):
    def setUp(self):
        super(CouponViewSetTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        course = CourseFactory(id='edx/Demo_Course/DemoX', partner=self.partner)
        self.seat = course.create_or_update_seat('verified', True, 50)

        self.catalog = Catalog.objects.create(partner=self.partner)
        self.coupon_data = {
            'title': 'Tešt Čoupon',
            'partner': self.partner,
            'benefit_type': Benefit.PERCENTAGE,
            'benefit_value': 100,
            'catalog': self.catalog,
            'end_datetime': str(now() + datetime.timedelta(days=10)),
            'enterprise_customer': {'id': str(uuid4())},
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
            'program_uuid': None,
            'sales_force_id': None,
            'salesforce_opportunity_line_item': None,
        }

    def test_clean_voucher_request_data(self):
        """
        Test that the method "clean_voucher_request_data" returns expected
        cleaned data dict.
        """
        title = 'Test coupon'
        stock_record = self.seat.stockrecords.first()
        self.coupon_data.update({
            'title': title,
            'client': 'Člient',
            'stock_record_ids': [stock_record.id],
            'voucher_type': Voucher.ONCE_PER_CUSTOMER,
            'price': 100,
            'category': {'name': self.category.name},
            'max_uses': 1,
            'notify_email': 'batman@gotham.comics',
            'sales_force_id': 'salesforceid123',
            'salesforce_opportunity_line_item': 'salesforcelineitem123',
        })
        view = CouponViewSet()
        cleaned_voucher_data = view.clean_voucher_request_data(self.coupon_data, self.site.siteconfiguration.partner)

        expected_cleaned_voucher_data_keys = [
            'benefit_type',
            'benefit_value',
            'coupon_catalog',
            'catalog_query',
            'category',
            'code',
            'course_catalog',
            'course_seat_types',
            'email_domains',
            'end_datetime',
            'enterprise_customer',
            'enterprise_customer_catalog',
            'enterprise_customer_name',
            'max_uses',
            'note',
            'partner',
            'prepaid_invoice_amount',
            'price',
            'quantity',
            'start_datetime',
            'title',
            'voucher_type',
            'program_uuid',
            'notify_email',
            'contract_discount_type',
            'contract_discount_value',
            'sales_force_id',
            'salesforce_opportunity_line_item',
        ]
        self.assertEqual(sorted(expected_cleaned_voucher_data_keys), sorted(cleaned_voucher_data.keys()))

    def test_clean_voucher_request_data_notify_email_validation_msg(self):
        """
        Test that the method "clean_voucher_request_data" raise ValidationError if notify_email is incorrect
        """
        title = 'Test coupon'
        self.coupon_data.update({
            'title': title,
            'client': 'Člient',
            'stock_record_ids': ['111'],
            'voucher_type': Voucher.ONCE_PER_CUSTOMER,
            'price': 100,
            'category': {'name': self.category.name},
            'max_uses': 1,
            'notify_email': 'batman',
        })
        view = CouponViewSet()
        with self.assertRaises(ValidationError) as ve:
            view.clean_voucher_request_data(self.coupon_data, self.site.siteconfiguration.partner)
        exception = ve.exception
        self.assertIn('Notification email must be a valid email address.', exception.message)

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
        request.site = SiteConfigurationFactory().site
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
class CouponViewSetFunctionalTest(CouponMixin, DiscoveryTestMixin, DiscoveryMockMixin, ThrottlingMixin,
                                  TestCase):
    """Test the coupon order creation functionality."""

    def setUp(self):
        super(CouponViewSetFunctionalTest, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

        __, seat = self.create_course_and_seat(course_id='edx/Demo_Course1/DemoX', price=50)
        __, other_seat = self.create_course_and_seat(course_id='edx/Demo_Course2/DemoX', price=100)

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
            'stock_record_ids': [seat.stockrecords.first().id, other_seat.stockrecords.first().id],
            'title': 'Tešt čoupon',
            'voucher_type': Voucher.SINGLE_USE,
            'sales_force_id': '006ABCDE0123456789',
            'salesforce_opportunity_line_item': '000ABCDE9876543210',
        }
        self.response = self.get_response('POST', COUPONS_LINK, self.data)
        self.coupon = Product.objects.get(title=self.data['title'])

    def assert_post_response_status(self, data, expected_status=status.HTTP_400_BAD_REQUEST):
        response = self.get_response('POST', COUPONS_LINK, data)
        self.assertEqual(response.status_code, expected_status)

    def get_response(self, method, path, data=None):
        """Helper method for sending requests and returning the response."""
        with mock.patch(
                "ecommerce.extensions.voucher.utils.get_enterprise_customer",
                mock.Mock(return_value={'name': 'Fake enterprise'})):
            if method == 'GET':
                return self.client.get(path)
            if method == 'POST':
                return self.client.post(path, json.dumps(data), 'application/json')
            if method == 'PUT':
                return self.client.put(path, json.dumps(data), 'application/json')
        return None

    def get_response_json(self, method, path, data=None):
        """Helper method for sending requests and returning JSON response content."""
        response = self.get_response(method, path, data)
        if response:
            return json.loads(response.content.decode('utf-8'))
        return None

    def _get_voucher_range_with_updated_dynamic_catalog_values(self):
        """Helper method for updating dynamic catalog values."""
        path = reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id})
        data = {
            'catalog_query': '*:*',
            'course_seat_types': ['verified'],
        }
        self.get_response('PUT', path, data)
        new_coupon = Product.objects.get(id=self.coupon.id)
        vouchers = new_coupon.attr.coupon_vouchers.vouchers
        return vouchers.first().offers.first().benefit.range, data

    def _create_and_get_coupon_details(self):
        """Helper method that creates and returns coupon details."""
        self.get_response('POST', COUPONS_LINK, self.data)
        coupon = Product.objects.get(title=self.data['title'])
        return self.get_response_json('GET', reverse('api:v2:coupons-detail', args=[coupon.id]))

    @ddt.data(
        (100, Benefit.PERCENTAGE, 'Enrollment code'),
        (100, Benefit.FIXED, 'Discount code'),
        (50, Benefit.PERCENTAGE, 'Discount code'),
        (50, Benefit.FIXED, 'Discount code'),
    )
    @ddt.unpack
    def test_regular_coupon_coupon_type(self, benefit_value, benefit_type, coupon_type):
        """Test that the correct coupon_type is returned after a simple coupon creation"""
        self.data.update({
            'benefit_value': benefit_value,
            'benefit_type': benefit_type,
            'title': 'Test Coupon Type'
        })
        details_response = self._create_and_get_coupon_details()
        self.assertEqual(details_response['coupon_type'], coupon_type)

    @ddt.data(
        (100, Benefit.PERCENTAGE, 'Enrollment code'),
        (100, Benefit.FIXED, 'Discount code'),
        (50, Benefit.PERCENTAGE, 'Discount code'),
        (50, Benefit.FIXED, 'Discount code'),
    )
    @ddt.unpack
    def test_enterprise_coupon_coupon_type(self, benefit_value, benefit_type, coupon_type):
        """Test that the correct coupon_type is returned after an enterprise coupon is created"""
        self.data.update({
            'benefit_value': benefit_value,
            'benefit_type': benefit_type
        })
        enterprise_customer_id = str(uuid4())
        enterprise_catalog_id = str(uuid4())
        enterprise_name = 'test enterprise'
        response = self._create_enterprise_coupon(
            enterprise_customer_id,
            enterprise_catalog_id,
            enterprise_name,
            ENTERPRISE_COUPONS_LINK
        )
        coupon_id = response.json()['coupon_id']
        details_response = self.get_response_json(
            'GET',
            reverse('api:v2:enterprise-coupons-detail', kwargs={'pk': coupon_id})
        )
        self.assertEqual(details_response['coupon_type'], coupon_type)

    def test_create_coupon_with_same_code_data(self):
        """
        Test creating discount coupon with same code again is invalid.
        """
        self.data.update({
            'benefit_value': 50,
            'code': '123456',
            'quantity': 1,
            'title': 'Test coupon'
        })
        response_data = self.get_response('POST', COUPONS_LINK, self.data)
        self.assertEqual(response_data.status_code, status.HTTP_200_OK)

        # now try to create discount coupon with same code again
        self.assert_post_response_status(self.data, status.HTTP_400_BAD_REQUEST)

    def test_create_coupon_product_invalid_category_data(self):
        """Test creating coupon when provided category data is invalid."""
        self.data.update({'category': {'id': 10000, 'name': 'Category Not Found'}})
        self.assert_post_response_status(self.data, status.HTTP_404_NOT_FOUND)

    @ddt.data(
        {'benefit_type': ''},
        {'benefit_type': 'foo'},
        {'benefit_value': ''},
        {'benefit_value': 'foo'},
        {'benefit_value': -1},
        {'benefit_value': 121},
        {'category': {'a': 'a', 'b': 'b'}},
        {'course_catalog': {'name': 'Invalid course catalog data dict without id key'}},
        {'enterprise_customer': {'name': 'Invalid Enterprise Customer data dict without id key'}},
    )
    def test_create_coupon_product_invalid_data(self, invalid_data):
        """Test creating coupon when provided data is invalid."""
        self.data.update(invalid_data)
        self.assert_post_response_status(self.data, status.HTTP_400_BAD_REQUEST)

    @ddt.data('benefit_type', 'benefit_value')
    def test_create_coupon_product_no_data_provided(self, key):
        """Test creating coupon when data is not provided in json."""
        del self.data[key]
        self.assert_post_response_status(self.data, status.HTTP_400_BAD_REQUEST)

    def test_response(self):
        """Test the response data given after the order was created."""
        basket = Basket.objects.last()
        order = Order.objects.last()

        self.assertEqual(self.response.status_code, status.HTTP_200_OK)
        response_data = self.response.json()
        expected = {
            'payment_data': {'payment_processor_name': 'Invoice'},
            'id': basket.id,
            'order': order.id,
            'coupon_id': self.coupon.id
        }
        self.assertDictEqual(response_data, expected)

    def test_order(self):
        """Test the order data after order creation."""
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Order.objects.first().status, 'Complete')
        self.assertEqual(Order.objects.first().lines.count(), 1)
        self.assertEqual(Order.objects.first().lines.first().product, self.coupon)

    def test_authentication_required(self):
        """Test that a guest cannot access the view."""
        self.assert_post_response_status(self.data, status.HTTP_200_OK)
        self.client.logout()
        self.assert_post_response_status(self.data, status.HTTP_401_UNAUTHORIZED)

    def test_authorization_required(self):
        """Test that a non-staff user cannot access the view."""
        user = self.create_user(is_staff=False)
        self.client.login(username=user.username, password=self.password)
        self.assert_post_response_status(self.data, status.HTTP_403_FORBIDDEN)

    def test_list_coupons(self):
        """The list endpoint should return only coupons with current site's partner."""
        self.create_coupon(partner=PartnerFactory())
        self.assertEqual(Product.objects.filter(product_class__name='Coupon').count(), 2)
        response = self.client.get(COUPONS_LINK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        coupon_data = json.loads(response.content.decode('utf-8'))['results'][0]
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
        details_response = self._create_and_get_coupon_details()
        self.assertEqual(details_response['code'], self.data['code'])
        self.assertEqual(details_response['coupon_type'], 'Discount code')

        list_response = self.client.get(COUPONS_LINK)
        coupon_data = json.loads(list_response.content.decode('utf-8'))['results'][0]
        self.assertEqual(coupon_data['code'], self.data['code'])

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

    def test_update_multi_offer_coupon(self):
        """Test updating a coupon that has unique offers under each offer."""
        self.data.update({
            'title': 'Test Multi Use Coupon Update',
            'quantity': 5,
            'voucher_type': Voucher.MULTI_USE,
            'max_uses': 10,
            'benefit_value': 10,
            'email_domains': 'edx.org'
        })

        self.get_response('POST', COUPONS_LINK, self.data)
        coupon = Product.objects.get(title=self.data['title'])
        vouchers = coupon.attr.coupon_vouchers.vouchers.all()
        offers = {}
        for voucher in vouchers:
            offer = voucher.offers.first()
            offers[offer.name] = offer
            self.assertEqual(offer.max_global_applications, 10)
            self.assertEqual(offer.email_domains, 'edx.org')
            self.assertEqual(offer.benefit.value, 10)
        self.assertEqual(len(list(offers.keys())), 5)

        self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id}),
            data={'benefit_value': 20, 'email_domains': '', 'max_uses': None}
        )
        updated_coupon = Product.objects.get(title=self.data['title'])
        self.assertEqual(coupon.id, updated_coupon.id)
        vouchers = updated_coupon.attr.coupon_vouchers.vouchers.all()
        offers = {}
        for voucher in vouchers:
            offer = voucher.offers.first()
            offers[offer.name] = offer
            self.assertEqual(offer.max_global_applications, None)
            self.assertEqual(offer.benefit.value, 20)
            self.assertEqual(offer.email_domains, '')
        self.assertEqual(len(list(offers.keys())), 5)

    def _create_enterprise_coupon(
            self, enterprise_customer_id, enterprise_catalog_id, enterprise_name, post_url=COUPONS_LINK):
        self.data.update({
            'title': 'Test Create Enterprise Coupon',
            'enterprise_customer': {'name': enterprise_name, 'id': enterprise_customer_id},
            'enterprise_customer_catalog': enterprise_catalog_id,
            'contract_discount_value': '12.34',
            'contract_discount_type': EnterpriseContractMetadata.PERCENTAGE,
            'prepaid_invoice_amount': '200000',
        })

        return self.get_response('POST', post_url, self.data)

    def _check_enterprise_fields(
            self,
            coupon,
            enterprise_customer_id,
            enterprise_catalog_id,
            enterprise_name):
        vouchers = coupon.attr.coupon_vouchers.vouchers.all()
        for voucher in vouchers:
            all_offers = voucher.offers.all()
            self.assertEqual(len(all_offers), 2)
            self.assertEqual(str(all_offers[0].condition.range.enterprise_customer),
                             enterprise_customer_id)
            self.assertEqual(
                str(all_offers[0].condition.range.enterprise_customer_catalog),
                enterprise_catalog_id)
            self.assertEqual(str(all_offers[1].condition.enterprise_customer_uuid),
                             enterprise_customer_id)
            self.assertEqual(
                str(all_offers[1].condition.enterprise_customer_catalog_uuid),
                enterprise_catalog_id)
            self.assertEqual(all_offers[1].condition.proxy_class,
                             class_path(AssignableEnterpriseCustomerCondition))

        # Check that the enterprise name took precedence as the client name
        basket = Basket.objects.filter(lines__product_id=coupon.id).first()
        invoice = Invoice.objects.get(order__basket=basket)
        self.assertEqual(invoice.business_client.name, enterprise_name)

    def test_list_coupons_with_enterprise_data(self):
        """Test list endpoint filters out enterprise coupons."""
        # Verify that the enterprise coupon gets filtered out
        response = self.client.get(COUPONS_LINK)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        coupon_data = json.loads(response.content.decode('utf-8'))['results']
        self.assertEqual(len(coupon_data), 1)
        self.assertEqual(coupon_data[0]['title'], self.data['title'])

    def test_create_enterprise_offers(self):
        """Test creating an enterprise coupon with the enterprise offers."""
        enterprise_customer_id = str(uuid4())
        enterprise_catalog_id = str(uuid4())
        enterprise_name = 'test enterprise'
        response = self._create_enterprise_coupon(enterprise_customer_id, enterprise_catalog_id, enterprise_name)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        content = response.json()
        self.assertEqual(content, 'Enterprise coupons can no longer be created or updated from this endpoint.')

    def test_update_enterprise_offers_regular_coupon(self):
        """Test updating a coupon to add enterprise data with the enterprise offers."""
        enterprise_customer_id = str(uuid4())
        enterprise_catalog_id = str(uuid4())
        self.get_response(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id}),
            data={
                'enterprise_customer': {'name': 'test enterprise', 'id': enterprise_customer_id},
                'enterprise_customer_catalog': enterprise_catalog_id,
            }
        )
        new_coupon = Product.objects.get(id=self.coupon.id)
        self.assertEqual(new_coupon.attr.enterprise_customer_uuid, enterprise_customer_id)
        self._check_enterprise_fields(new_coupon, enterprise_customer_id, enterprise_catalog_id, 'test enterprise')

    def test_update_enterprise_offers_enterprise_coupon(self):
        """Test updating an enterprise coupon with the enterprise offers."""
        enterprise_customer_id = str(uuid4())
        enterprise_catalog_id = str(uuid4())
        enterprise_name = 'test enterprise'
        self._create_enterprise_coupon(
            enterprise_customer_id, enterprise_catalog_id, enterprise_name, ENTERPRISE_COUPONS_LINK
        )
        coupon = Product.objects.get(title=self.data['title'])

        response = self.get_response(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': coupon.id}),
            data={
                'title': 'Updated Enterprise Coupon',
            }
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

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
        self.get_response('PUT', path, data)

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
        self.get_response('PUT', path, data)

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
        self.get_response('PUT', path, data)

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
        self.get_response('PUT', path, data)

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
        self.get_response('PUT', path, data)

        new_coupon = Product.objects.get(id=self.coupon.id)
        self.assertEqual(new_coupon.attr.note, note)

    @ddt.data(
        '006abcde0123456789', 'otherSalesForce', ''
    )
    def test_update_sales_force_id(self, sales_force_id):
        """
        Test sales force id update.
        """
        path = reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id})
        data = {
            'sales_force_id': sales_force_id
        }
        response = self.get_response('PUT', path, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        new_coupon = Product.objects.get(id=self.coupon.id)
        if sales_force_id:
            self.assertEqual(new_coupon.attr.sales_force_id, sales_force_id)

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

    def test_update_course_catalog_coupon(self):
        """
        Test that on updating a coupon as course catalog coupon with course
        seats, deletes values for fields "catalog" and "catalog_query" from its
        related voucher range.
        """
        path = reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id})
        course_catalog = {'id': 1, 'name': 'Test catalog'}
        course_seat_types = ['verified']

        data = {
            'id': self.coupon.id,
            'course_catalog': course_catalog,
            'course_seat_types': course_seat_types,
        }
        self.get_response('PUT', path, data)

        updated_coupon = Product.objects.get(id=self.coupon.id)
        vouchers = updated_coupon.attr.coupon_vouchers.vouchers
        voucher_range = vouchers.first().offers.first().benefit.range

        expected_course_seat_types = ','.join(course_seat_types)
        self.assertEqual(voucher_range.catalog, None)
        self.assertEqual(voucher_range.catalog_query, None)
        self.assertEqual(voucher_range.course_seat_types, expected_course_seat_types)
        self.assertEqual(voucher_range.course_catalog, course_catalog['id'])

    def test_update_course_catalog_coupon_without_seat_types(self):
        """
        Test that on updating a coupon as a course catalog coupon without any
        course seat types, a validation error message is logged along with a
        400 http response.
        """
        path = reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id})

        data = {
            'id': self.coupon.id,
            'course_catalog': {'id': 1, 'name': 'Test catalog'},
            'course_seat_types': [],
        }

        logger_name = 'ecommerce.core.utils'
        expected_logger_message = 'Failed to create Range. Either catalog_query or course_catalog must be given ' \
                                  'but not both and course_seat_types fields must be set.'
        with LogCapture(logger_name) as logger:
            response = self.get_response('PUT', path, data)

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            logger.check(
                (
                    logger_name,
                    'ERROR',
                    expected_logger_message
                )
            )

    def test_update_coupon_benefit_value(self):
        vouchers = self.coupon.attr.coupon_vouchers.vouchers.all()
        max_uses = vouchers[0].offers.first().max_global_applications
        benefit_value = Decimal(54)

        with mock.patch(
                "ecommerce.extensions.voucher.utils.get_enterprise_customer",
                mock.Mock(return_value={'name': 'Fake enterprise'})):
            CouponViewSet().update_offer_data(
                request_data={'benefit_value': benefit_value},
                vouchers=vouchers,
                site=self.site,
            )
        for voucher in vouchers:
            self.assertEqual(voucher.offers.first().benefit.value, benefit_value)
            self.assertEqual(voucher.offers.first().max_global_applications, max_uses)

    def test_update_coupon_client(self):
        baskets = Basket.objects.filter(lines__product_id=self.coupon.id)
        basket = baskets.first()
        client_username = 'Tešt Člient Ušername'
        CouponViewSet().update_coupon_product_data(
            request_data={'client': client_username},
            coupon=self.coupon
        )

        invoice = Invoice.objects.get(order__basket=basket)
        self.assertEqual(invoice.business_client.name, client_username)

    def test_update_coupon_inactive(self):
        """Test update inactive flag of Coupon, also test code_status"""
        # test ACTIVE
        data = {
            'id': self.coupon.id,
            'inactive': True
        }
        response_data = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id}),
            data=data
        )
        self.assertEqual(response_data['code_status'], 'INACTIVE')
        self.assertEqual(response_data['inactive'], True)
        self.assertEqual(self.coupon.attr.inactive, True)

        # test INACTIVE
        data['inactive'] = False
        response_data = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id}),
            data=data
        )
        coupon = Product.objects.get(pk=self.coupon.id)  # fresh form db
        self.assertEqual(response_data['code_status'], 'ACTIVE')
        self.assertEqual(response_data['inactive'], False)
        self.assertEqual(coupon.attr.inactive, False)

        # test EXPIRED
        data = {
            'id': self.coupon.id,
            'end_datetime': str(now() - datetime.timedelta(days=1))
        }
        response_data = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id}),
            data=data
        )
        self.assertEqual(response_data['code_status'], 'EXPIRED')

    def test_update_invoice_data(self):
        invoice = Invoice.objects.get(order__lines__product=self.coupon)
        self.assertEqual(invoice.discount_type, Invoice.PERCENTAGE)
        CouponViewSet().update_invoice_data(
            coupon=self.coupon,
            request_data={
                'invoice_discount_type': Invoice.FIXED
            }
        )

        invoice = Invoice.objects.get(order__lines__product=self.coupon)
        self.assertEqual(invoice.discount_type, Invoice.FIXED)

    @ddt.data('audit', 'honor')
    def test_restricted_course_mode(self, mode):
        """Test that an exception is raised when a black-listed course mode is used."""
        course = CourseFactory(id='black/list/mode', partner=self.partner)
        seat = course.create_or_update_seat(mode, False, 0)
        # Seats derived from a migrated "audit" mode do not have a certificate_type attribute.
        if mode == 'audit':
            seat = ProductFactory()
        self.data.update({'stock_record_ids': [StockRecord.objects.get(product=seat).id]})
        self.assert_post_response_status(self.data)

    @responses.activate
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
        self.mock_access_token_response()
        self.mock_course_runs_endpoint(
            self.site_configuration.discovery_api_url, query=catalog_query, course_run=course
        )

        response = self.get_response('POST', COUPONS_LINK, self.data)
        coupon_id = response.json()['coupon_id']
        details_response = self.client.get(reverse('api:v2:coupons-detail', args=[coupon_id]))
        detail = json.loads(details_response.content.decode('utf-8'))
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
        self.assertEqual(voucher.offers.first().max_global_applications, max_uses)

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

        response = self.get_response('POST', COUPONS_LINK, self.data)
        coupon_id = response.json()['coupon_id']

        details_response = self.client.get(reverse('api:v2:coupons-detail', args=[coupon_id]))
        return json.loads(details_response.content.decode('utf-8'))

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
        self.data.update({
            'max_uses': 3,
            'title': 'Max uses update',
            'voucher_type': Voucher.MULTI_USE
        })
        details = self._create_and_get_coupon_details()
        self.assertEqual(details['max_uses'], self.data['max_uses'])

        self.data['max_uses'] = 5
        response = self.get_response_json('PUT', reverse('api:v2:coupons-detail', args=[details['id']]), self.data)
        self.assertEqual(response['max_uses'], self.data['max_uses'])

    def test_create_coupon_without_category(self):
        """ Verify creating coupon without category returns bad request. """
        del self.data['category']
        self.assert_post_response_status(self.data)

    def test_create_coupon_with_category_not_dict(self):
        """ Verify creating coupon with category not being a dictionary returns bad request. """
        self.data['category'] = 'String type'
        self.assert_post_response_status(self.data)

    def test_creating_enrollment_coupon_with_code(self):
        """ Test that bad request status is returned when creating enrollment coupon with code parameter set. """
        self.data.update({'code': 'test'})
        self.assert_post_response_status(self.data)

    def test_creating_coupon_with_code_and_quantity_greater_than_one(self):
        """
        Test that bad request status is returned when creating discount coupon
        with code set and quantity greater than one.
        """
        self.data.update({
            'benefit_value': 90,
            'code': 'test',
            'quantity': 5
        })
        self.assert_post_response_status(self.data)

    @ddt.data(8, 'string', {'dict': 'type'})
    def test_creating_coupon_with_wrong_course_seat_types(self, course_seat_types):
        """ Verify creating coupon with course seat types not a list returns bad request. """
        self.data.update({'course_seat_types': course_seat_types})
        self.assert_post_response_status(self.data)

    def test_creating_coupon_with_course_seat_types(self):
        """ Verify creating coupon with course seat types list creates coupon. """
        self.data.update({
            'catalog_query': 'test',
            'course_seat_types': ['verified'],
            'stock_record_ids': None
        })
        self.assert_post_response_status(self.data, status.HTTP_200_OK)

    def test_create_single_use_coupon_with_max_uses(self):
        """Verify creating coupon with max uses field and single use voucher type returns 400 response."""
        self.data.update({
            'max_uses': 8,
            'voucher_type': Voucher.SINGLE_USE
        })
        self.assert_post_response_status(self.data, status.HTTP_400_BAD_REQUEST)

    def test_update_single_use_coupon_with_max_uses(self):
        """Verify updating coupon with max_uses field and single use voucher type returns 400 response."""
        details = self.get_response_json('GET', reverse('api:v2:coupons-detail', args=[self.coupon.id]))
        self.assertEqual(details['voucher_type'], Voucher.SINGLE_USE)

        self.data['max_uses'] = 9
        response = self.get_response(
            'PUT',
            reverse('api:v2:coupons-detail', args=[self.coupon.id]),
            self.data
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @ddt.data(6, '6')
    def test_create_multi_use_coupon_with_max_uses(self, max_uses):
        """Verify creating coupon with max uses field and multi-use voucher type."""
        self.data.update({
            'max_uses': max_uses,
            'voucher_type': Voucher.MULTI_USE
        })
        self.assert_post_response_status(self.data, status.HTTP_200_OK)

    @ddt.data(-3, 0, '', 'string')
    def test_create_coupon_with_invalid_max_uses(self, max_uses):
        """Verify creating coupon with invalid max uses field returns 400 response."""
        self.data.update({
            'max_uses': max_uses,
            'voucher_type': Voucher.MULTI_USE
        })
        self.assert_post_response_status(self.data)

    @ddt.data(-3, 0, '', 'string')
    def test_update_coupon_with_invalid_max_uses(self, max_uses):
        """Verify updating coupon with invalid max_uses field returns 400 response."""
        self.data.update({
            'max_uses': 2,
            'title': 'Coupon update with max uses {}'.format(max_uses),
            'voucher_type': Voucher.MULTI_USE
        })
        details = self._create_and_get_coupon_details()
        self.assertEqual(details['max_uses'], 2)

        self.data.update({'max_uses': max_uses})
        response = self.get_response(
            'PUT',
            reverse('api:v2:coupons-detail', args=[details['id']]),
            self.data
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @ddt.data(1, {'some': 'dict'}, ['array'])
    def test_create_coupon_with_invalid_note(self, invalid_note):
        """Verify creating coupon with invalid note field returns 400 response."""
        self.data['note'] = invalid_note
        self.assert_post_response_status(self.data)

    @ddt.data(1, {'some': 'dict'}, ['array'])
    def test_update_coupon_with_invalid_note(self, invalid_note):
        """Verify updating coupon with invalid note field returns 400 response."""
        self.data.update({
            'note': 'Some valid note.',
            'title': 'Coupon update with note {}'.format(invalid_note),
        })
        details = self._create_and_get_coupon_details()
        self.assertEqual(details['note'], self.data['note'])

        self.data['note'] = invalid_note
        response = self.get_response(
            'PUT',
            reverse('api:v2:coupons-detail', args=[details['id']]),
            self.data
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_coupon_with_program_uuid(self):
        """Verify create coupon with program uuid."""
        proxy_class = class_path(BENEFIT_MAP[self.data['benefit_type']])
        self.data.update({
            'program_uuid': str(uuid4()),
            'title': 'Program Coupon',
            'stock_record_ids': []
        })
        self.assertEqual(Benefit.objects.filter(proxy_class=proxy_class).count(), 0)
        self.assertEqual(Condition.objects.filter(program_uuid=self.data['program_uuid']).count(), 0)

        details = self._create_and_get_coupon_details()
        self.assertEqual(details['program_uuid'], self.data['program_uuid'])
        self.assertEqual(details['title'], self.data['title'])
        self.assertEqual(Benefit.objects.filter(proxy_class=proxy_class).count(), 1)
        self.assertEqual(Condition.objects.filter(program_uuid=self.data['program_uuid']).count(), 1)

    def test_update_coupon_with_program_uuid(self):
        """Verify update coupon program uuid."""
        program_uuid = str(uuid4())
        proxy_class = class_path(BENEFIT_MAP[self.data['benefit_type']])
        self.data.update({
            'program_uuid': program_uuid,
            'title': 'Program Coupon',
            'stock_record_ids': []
        })
        self.assertEqual(Benefit.objects.filter(proxy_class=proxy_class).count(), 0)
        self.assertEqual(Condition.objects.filter(program_uuid=self.data['program_uuid']).count(), 0)

        details = self._create_and_get_coupon_details()
        self.assertEqual(details['program_uuid'], program_uuid)
        self.assertEqual(details['title'], self.data['title'])
        self.assertEqual(Benefit.objects.filter(proxy_class=proxy_class).count(), 1)
        self.assertEqual(Condition.objects.filter(program_uuid=self.data['program_uuid']).count(), 1)

        edited_program_uuid = str(uuid4())
        coupon = Product.objects.get(title=self.data['title'])
        response_data = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': coupon.pk}),
            data={'program_uuid': edited_program_uuid}
        )
        self.assertEqual(response_data['program_uuid'], edited_program_uuid)
        self.assertEqual(response_data['title'], self.data['title'])
        self.assertEqual(Benefit.objects.filter(proxy_class=proxy_class).count(), 1)
        self.assertEqual(Condition.objects.filter(program_uuid=edited_program_uuid).count(), 1)

    def test_update_program_coupon_benefit_value(self):
        """Verify update benefit value for program coupon."""
        self.data.update({
            'program_uuid': str(uuid4()),
            'title': 'Program Coupon',
            'stock_record_ids': []
        })
        self.get_response('POST', COUPONS_LINK, self.data)

        edited_benefit_value = 92
        coupon = Product.objects.get(title=self.data['title'])
        response_data = self.get_response_json(
            'PUT',
            reverse('api:v2:coupons-detail', kwargs={'pk': coupon.pk}),
            data={'benefit_value': edited_benefit_value}
        )
        self.assertEqual(response_data['benefit_value'], edited_benefit_value)

    @ddt.data(Benefit.PERCENTAGE, Benefit.FIXED)
    def test_program_coupon_benefit_type(self, benefit_type):
        """Verify that the coupon serializer returns benefit type for program coupons."""
        self.data.update({
            'benefit_type': benefit_type,
            'program_uuid': str(uuid4()),
            'title': 'Test Program Coupon Benefit Type',
            'stock_record_ids': [],
        })
        details = self._create_and_get_coupon_details()
        self.assertEqual(details['benefit_type'], benefit_type)

    def test_update_notify_email(self):
        path = reverse('api:v2:coupons-detail', kwargs={'pk': self.coupon.id})
        notify_email = 'batman@gotham.comics'
        data = {
            'id': self.coupon.id,
            'notify_email': notify_email
        }
        self.get_response('PUT', path, data)

        coupon = Product.objects.get(id=self.coupon.id)
        self.assertEqual(coupon.attr.notify_email, notify_email)

    def test_create_coupon_with_contract_discount_metadata(self):
        """
        Verify a fresh enterprise coupon being created get a contract discount
        metadata object attached to its attributes.
        """

        enterprise_customer_id = str(uuid4())
        enterprise_catalog_id = str(uuid4())
        enterprise_name = 'test enterprise'
        response = self._create_enterprise_coupon(
            enterprise_customer_id,
            enterprise_catalog_id,
            enterprise_name,
            ENTERPRISE_COUPONS_LINK
        )
        coupon = Product.objects.get(id=response.json()['coupon_id'])
        assert coupon.attr.enterprise_contract_metadata.discount_value == Decimal('12.34000')
        assert coupon.attr.enterprise_contract_metadata.discount_type == 'Percentage'
        assert coupon.attr.enterprise_contract_metadata.amount_paid == Decimal('200000.00')

    def test_update_coupon_with_contract_discount_metadata(self):
        """
        Verify an update of an existing coupon that has DOES have contract metadata
        successfully updates contract metadata object to the coupon's attributes.
        """
        enterprise_customer_id = str(uuid4())
        enterprise_catalog_id = str(uuid4())
        enterprise_name = 'test enterprise'
        response = self._create_enterprise_coupon(
            enterprise_customer_id,
            enterprise_catalog_id,
            enterprise_name,
            ENTERPRISE_COUPONS_LINK
        )
        coupon_id = response.json()['coupon_id']

        coupon = Product.objects.get(id=coupon_id)
        assert coupon.attr.enterprise_contract_metadata.discount_value == Decimal('12.34000')
        assert coupon.attr.enterprise_contract_metadata.discount_type == 'Percentage'
        assert coupon.attr.enterprise_contract_metadata.amount_paid == Decimal('200000.00')

        dtype = EnterpriseContractMetadata.FIXED
        path = reverse('api:v2:enterprise-coupons-detail', kwargs={'pk': coupon_id})
        data = {
            'contract_discount_value': '1928374',
            'contract_discount_type': dtype,
            'prepaid_invoice_amount': '99009900'
        }
        self.get_response('PUT', path, data)

        coupon.attr.enterprise_contract_metadata.refresh_from_db()
        assert coupon.attr.enterprise_contract_metadata.discount_value == Decimal('1928374.00')
        assert coupon.attr.enterprise_contract_metadata.discount_type == dtype
        assert coupon.attr.enterprise_contract_metadata.amount_paid == Decimal('99009900.00')


class CouponCategoriesListViewTests(TestCase):
    """ Tests for the coupon category list view. """
    path = reverse('api:v2:coupons:coupons_categories')

    def setUp(self):
        super(CouponCategoriesListViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def test_category_list(self):
        """ Verify the endpoint returns successfully. """
        response = self.client.get(self.path + '?page_size=200')
        response_data = response.json()
        received_coupon_categories = {category['name'] for category in response_data['results']}
        self.assertCountEqual(TEST_CATEGORIES, received_coupon_categories)
        self.assertEqual(response_data['count'], 26)

    def test_deprecated_category_filtering(self):
        """ Verify the endpoint doesn't return deprecated coupon categories. """
        response = self.client.get(self.path)
        response_data = response.json()
        received_coupon_categories = [category['name'] for category in response_data['results']]
        self.assertFalse(any(coupon in received_coupon_categories for coupon in DEPRECATED_COUPON_CATEGORIES))
