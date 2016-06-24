from __future__ import unicode_literals

import json
import mock

import ddt
import httpretty
from django.core.urlresolvers import reverse
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_model
from oscar.test.factories import ConditionalOfferFactory, RangeFactory, VoucherFactory
from requests.exceptions import ConnectionError, Timeout
from rest_framework.test import APIRequestFactory
from slumber.exceptions import SlumberBaseException

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.coupons.tests.mixins import CatalogPreviewMockMixin
from ecommerce.coupons.views import get_voucher_and_products_from_code
from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.v2.views.vouchers import VoucherViewSet
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.partner.models import StockRecord
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.coupons.tests.mixins import CouponMixin
from ecommerce.courses.models import Course
from ecommerce.tests.mixins import Catalog, LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

COUPON_CODE = 'COUPONCODE'


Range = get_model('offer', 'Range')
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
class VoucherViewOffersEndpointTests(
        CatalogPreviewMockMixin,
        CouponMixin,
        CourseCatalogTestMixin,
        LmsApiMockMixin,
        TestCase
):
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

    def test_voucher_offers_listing_for_a_single_course_voucher(self):
        """ Verify the endpoint returns offers data when a single product is in voucher range. """
        course, seat = self.create_course_and_seat()
        self.mock_course_api_response(course=course)
        new_range = RangeFactory(products=[seat, ])
        new_range.catalog = Catalog.objects.create(partner=self.partner)
        new_range.catalog.stock_records.add(StockRecord.objects.get(product=seat))
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        request = self.prepare_offers_listing_request(voucher.code)
        response = self.endpointView(request)

        self.assertEqual(response.status_code, 200)

        # If no seat is associated with the voucher range, Bad Request status should be returned
        new_range.remove_product(seat)
        response = self.endpointView(request)
        self.assertEqual(response.status_code, 400)

    @ddt.data((ConnectionError,), (Timeout,), (SlumberBaseException,))
    @ddt.unpack
    def test_voucher_offers_listing_api_exception_caught(self, exception):
        """ Verify the endpoint returns status 400 Bad Request when ConnectionError occurs """
        with mock.patch(
            'ecommerce.extensions.api.v2.views.vouchers.VoucherViewSet.get_offers',
            mock.Mock(side_effect=exception)
        ):
            __, seat = self.create_course_and_seat()
            new_range = RangeFactory(products=[seat, ])
            voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
            request = self.prepare_offers_listing_request(voucher.code)
            response = self.endpointView(request)

            self.assertEqual(response.status_code, 400)

    @mock_course_catalog_api_client
    def test_voucher_offers_listing_product_found(self):
        """ Verify the endpoint returns offers data for single product range. """
        course, seat = self.create_course_and_seat()
        self.mock_course_api_response(course=course)

        new_range = RangeFactory(products=[seat, ])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        request = self.prepare_offers_listing_request(voucher.code)
        response = self.endpointView(request)

        self.assertEqual(response.status_code, 200)

    @mock_course_catalog_api_client
    def test_voucher_offers_listing_catalog_query(self):
        """ Verify the endpoint returns offers data for single product range. """
        course, seat = self.create_course_and_seat()
        self.mock_dynamic_catalog_course_runs_api(query='*:*', course_run=course)
        new_range, __ = Range.objects.get_or_create(catalog_query='*:*')
        new_range.add_product(seat)
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        voucher, __ = get_voucher_and_products_from_code(voucher.code)
        request = self.prepare_offers_listing_request(voucher.code)
        response = self.endpointView(request)

        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)
        # More assertions here

    @mock_course_catalog_api_client
    def test_get_offers_for_single_course_voucher(self):
        """ Verify that the course offers data is returned for a single course voucher. """
        course, seat = self.create_course_and_seat()
        new_range = RangeFactory(products=[seat, ])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        voucher, products = get_voucher_and_products_from_code(voucher.code)
        benefit = voucher.offers.first().benefit
        request = self.prepare_offers_listing_request(voucher.code)
        self.mock_course_api_response(course=course)
        offers = VoucherViewSet().get_offers(products=products, request=request, voucher=voucher)
        first_offer = offers[0]

        self.assertEqual(len(offers), 1)
        self.assertDictEqual(first_offer, {
            'benefit': {
                'type': benefit.type,
                'value': benefit.value
            },
            'contains_verified': True,
            'course_start_date': '2013-02-05T05:00:00Z',
            'id': course.id,
            'image_url': 'path/to/the/course/image',
            'organization': CourseKey.from_string(course.id).org,
            'seat_type': course.type,
            'stockrecords': serializers.StockRecordSerializer(seat.stockrecords.first()).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime
        })

    @mock_course_catalog_api_client
    def test_get_offers_for_multiple_courses_voucher(self):
        """ Verify that the course offers data is returned for a multiple courses voucher. """
        course, seat = self.create_course_and_seat()
        self.mock_dynamic_catalog_course_runs_api(query='*:*', course_run=course)
        new_range, __ = Range.objects.get_or_create(catalog_query='*:*')
        new_range.add_product(seat)
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        voucher, products = get_voucher_and_products_from_code(voucher.code)
        benefit = voucher.offers.first().benefit
        request = self.prepare_offers_listing_request(voucher.code)
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
            'image_url': 'path/to/the/course/image',
            'organization': CourseKey.from_string(course.id).org,
            'seat_type': course.type,
            'stockrecords': serializers.StockRecordSerializer(seat.stockrecords.first()).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime
        })

    def test_get_offers_for_product_exception_paths(self):
        course, seat = self.create_course_and_seat()
        new_range = RangeFactory(products=[seat, ])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        voucher, products = get_voucher_and_products_from_code(voucher.code)
        request = self.prepare_offers_listing_request(voucher.code)
        self.mock_course_api_response(course=course)
        offers = VoucherViewSet().get_offers(products=products, request=request, voucher=voucher)

        with mock.patch('ecommerce.extensions.api.v2.views.vouchers.Course.objects.get') as mock_get:
            mock_get.side_effect = Course.DoesNotExist
            offers = VoucherViewSet()._get_offers_for_product(products[0], voucher)  # pylint:disable=protected-access
            self.assertEqual(len(offers), 0)

        with mock.patch('ecommerce.extensions.api.v2.views.vouchers.StockRecord.objects.get') as mock_get:
            mock_get.side_effect = StockRecord.DoesNotExist
            offers = VoucherViewSet()._get_offers_for_product(products[0], voucher)  # pylint:disable=protected-access
            self.assertEqual(len(offers), 0)

        offers = VoucherViewSet().get_offers(products=[], request=request, voucher=voucher)
        self.assertEqual(len(offers), 0)

        offers = VoucherViewSet().get_offers(products=products, request=request, voucher=None)
        self.assertEqual(len(offers), 0)
