from __future__ import unicode_literals

import json

import ddt
import httpretty
from django.core.urlresolvers import reverse
from django.test import RequestFactory
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_model
from oscar.test.factories import ConditionalOfferFactory, ProductFactory, RangeFactory, VoucherFactory

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.coupons.tests.mixins import CatalogPreviewMockMixin
from ecommerce.coupons.views import get_voucher_from_code
from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.v2.views.vouchers import VoucherViewSet
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.tests.testcases import TestCase


StockRecord = get_model('partner', 'StockRecord')


@ddt.ddt
class VoucherViewSetTests(CouponMixin, CourseCatalogTestMixin, CatalogPreviewMockMixin, TestCase):
    """ Tests for the VoucherViewSet view set. """
    coupon_code = 'COUPONCODE'
    path = reverse('api:v2:vouchers-list')

    def setUp(self):
        super(VoucherViewSetTests, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)
        voucher1 = VoucherFactory()
        voucher1.offers.add(ConditionalOfferFactory())
        self.voucher = VoucherFactory(code=self.coupon_code)
        self.voucher.offers.add(ConditionalOfferFactory(name='test2'))

    def prepare_offers_listing_request(self, code):
        factory = RequestFactory()
        request = factory.get('/api/v2/vouchers/offers/?code={}'.format(code))
        request.site = self.site
        return request

    def test_voucher_listing(self):
        """ Verify the endpoint lists out all vouchers. """
        response = self.client.get(self.path)
        response_data = json.loads(response.content)

        self.assertEqual(response_data['count'], 2)
        self.assertEqual(response_data['results'][1]['code'], self.coupon_code)

    def test_voucher_filtering(self):
        """ Verify the endpoint filters by code. """
        filter_path = '{}?code={}'.format(self.path, self.coupon_code)
        response = self.client.get(filter_path)
        response_data = json.loads(response.content)

        self.assertEqual(response_data['count'], 1)
        self.assertEqual(response_data['results'][0]['code'], self.coupon_code)

    @ddt.data(('COUPONCODE',), ('NOT_FOUND_CODE',))
    @ddt.unpack
    def test_voucher_offers_listing_product_not_found(self, code):
        """ Verify the endpoint returns status 400 Bad Request. """
        request = self.prepare_offers_listing_request(code)
        response = VoucherViewSet().offers(request)

        self.assertEqual(response.status_code, 400)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_voucher_offers_listing_product_found(self):
        """ Verify the endpoint returns offers data. """
        self.mock_dynamic_catalog_course_runs_api()
        product = ProductFactory(stockrecords__price_excl_tax=100)
        new_range = RangeFactory(products=[product, ])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        request = self.prepare_offers_listing_request(voucher.code)
        response = VoucherViewSet().offers(request)

        self.assertEqual(response.status_code, 200)

    @httpretty.activate
    @mock_course_catalog_api_client
    def test_get_offers(self):
        """ Verify that the course offers data is returned. """
        course, seat = self.create_course_and_seat()
        new_range = RangeFactory(products=[seat, ])
        voucher, coupon = prepare_voucher(_range=new_range, benefit_value=10)
        voucher, products = get_voucher_from_code(voucher.code)
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
            'course_start_date': self.COURSE_START_DATE,
            'id': course.id,
            'image_url': self.COURSE_IMAGE_SRC,
            'organization': CourseKey.from_string(course.id).org,
            'seat_type': course.type,
            'stockrecords': serializers.StockRecordSerializer(seat.stockrecords.first()).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime
        })
