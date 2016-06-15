from __future__ import unicode_literals

import json

import ddt
import httpretty
from django.core.urlresolvers import reverse
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_model
from oscar.test.factories import ConditionalOfferFactory, ProductFactory, RangeFactory, VoucherFactory
from rest_framework.test import APIRequestFactory

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.coupons.tests.mixins import CatalogPreviewMockMixin
from ecommerce.coupons.views import get_voucher_and_products_from_code
from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.v2.views.vouchers import VoucherViewSet
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.tests.mixins import Catalog
from ecommerce.tests.testcases import TestCase

COUPON_CODE = 'COUPONCODE'


StockRecord = get_model('partner', 'StockRecord')


class VoucherViewSetTests(TestCase):
    """ Tests for the VoucherViewSet view set. """
    path = reverse('api:v2:vouchers-list')

    def setUp(self):
        super(VoucherViewSetTests, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        voucher1 = VoucherFactory()
        voucher1.offers.add(ConditionalOfferFactory())
        self.voucher = VoucherFactory(code=COUPON_CODE)
        self.voucher.offers.add(ConditionalOfferFactory(name='test2'))

    def test_voucher_listing(self):
        """ Verify the endpoint lists out all vouchers. """
        response = self.client.get(self.path)
        response_data = json.loads(response.content)

        self.assertEqual(response_data['count'], 2)
        self.assertEqual(response_data['results'][1]['code'], COUPON_CODE)

    def test_voucher_filtering(self):
        """ Verify the endpoint filters by code. """
        filter_path = '{}?code={}'.format(self.path, COUPON_CODE)
        response = self.client.get(filter_path)
        response_data = json.loads(response.content)

        self.assertEqual(response_data['count'], 1)
        self.assertEqual(response_data['results'][0]['code'], COUPON_CODE)


@ddt.ddt
@httpretty.activate
class VoucherViewOffersEndpointTests(CatalogPreviewMockMixin, CouponMixin, CourseCatalogTestMixin, TestCase):
    """ Tests for the VoucherViewSet offers endpoint. """

    def setUp(self):
        super(VoucherViewOffersEndpointTests, self).setUp()
        self.endpointView = VoucherViewSet.as_view({'get': 'offers'})
        self.factory = APIRequestFactory()
        request = self.factory.get('/page=1')
        self.endpointView.request = request

    def prepare_offers_listing_request(self, code):
        factory = APIRequestFactory()
        request = factory.get('/?code={}&page_size=6'.format(code))
        request.site = self.site
        return request

    @ddt.data(('COUPONCODE',), ('NOT_FOUND_CODE',))
    @ddt.unpack
    def test_voucher_offers_listing_product_not_found(self, code):
        """ Verify the endpoint returns status 400 Bad Request. """
        request = self.prepare_offers_listing_request(code)
        response = VoucherViewSet().offers(request)

        self.assertEqual(response.status_code, 400)

    @mock_course_catalog_api_client
    def test_voucher_offers_listing_with_range_catalog(self):
        """ Verify the endpoint returns offers data when range has a catalog. """
        self.mock_dynamic_catalog_course_runs_api()
        product = ProductFactory(stockrecords__price_excl_tax=100)
        new_range = RangeFactory(products=[product, ])
        new_range.catalog = Catalog.objects.create(partner=self.partner)
        new_range.catalog.stock_records.add(StockRecord.objects.get(product=product))
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        request = self.prepare_offers_listing_request(voucher.code)
        response = self.endpointView(request)

        self.assertEqual(response.status_code, 200)

        # If no product is associated with the voucher range, Bad Request status should be returned
        new_range.remove_product(product)
        response = self.endpointView(request)
        self.assertEqual(response.status_code, 400)

    @mock_course_catalog_api_client
    def test_voucher_offers_listing_product_found(self):
        """ Verify the endpoint returns offers data for single product range. """
        self.mock_dynamic_catalog_course_runs_api()
        product = ProductFactory(stockrecords__price_excl_tax=100)
        new_range = RangeFactory(products=[product, ])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        request = self.prepare_offers_listing_request(voucher.code)
        response = self.endpointView(request)

        self.assertEqual(response.status_code, 200)

    @mock_course_catalog_api_client
    def test_get_offers(self):
        """ Verify that the course offers data is returned. """
        course, seat = self.create_course_and_seat()
        new_range = RangeFactory(products=[seat, ])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        voucher, products = get_voucher_and_products_from_code(voucher.code)
        benefit = voucher.offers.first().benefit
        request = self.prepare_offers_listing_request(voucher.code)
        self.mock_dynamic_catalog_course_runs_api(course_run=course, query=new_range.catalog_query)
        offers = VoucherViewSet().get_offers(products=products, request=request, voucher=voucher)
        first_offer = offers[0]

        self.assertEqual(len(offers), 1)
        self.assertDictEqual(first_offer, {
            'benefit': {
                'type': benefit.type,
                'value': benefit.value
            },
            'contains_verified': True,
            'course_start_date': '2016-05-01T00:00:00Z',
            'id': course.id,
            'image_url': 'http://127.0.0.1:8000/asset-v1:edX+DemoX+Demo_Course+type@asset+block@_course_image.jpg',
            'organization': CourseKey.from_string(course.id).org,
            'seat_type': course.type,
            'stockrecords': serializers.StockRecordSerializer(seat.stockrecords.first()).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime
        })
