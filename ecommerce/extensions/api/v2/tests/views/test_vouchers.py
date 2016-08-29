from __future__ import unicode_literals

import datetime
import json
import mock

import ddt
import httpretty
import pytz
from django.core.urlresolvers import reverse
from django.http import Http404
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_model
from oscar.test.factories import BenefitFactory, ConditionalOfferFactory, RangeFactory, VoucherFactory
from requests.exceptions import ConnectionError, Timeout
from rest_framework.test import APIRequestFactory
from slumber.exceptions import SlumberBaseException

from ecommerce.core.tests.decorators import mock_course_catalog_api_client
from ecommerce.core.url_utils import get_lms_url
from ecommerce.coupons.tests.mixins import CourseCatalogMockMixin, CouponMixin
from ecommerce.coupons.views import get_voucher_and_products_from_code
from ecommerce.courses.models import Course
from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.v2.views.vouchers import VoucherViewSet
from ecommerce.extensions.catalogue.tests.mixins import CourseCatalogTestMixin
from ecommerce.extensions.partner.strategy import DefaultStrategy
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.mixins import Catalog, LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

COUPON_CODE = 'COUPONCODE'


Range = get_model('offer', 'Range')
StockRecord = get_model('partner', 'StockRecord')


class VoucherViewSetTests(CourseCatalogMockMixin, CourseCatalogTestMixin, TestCase):
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

    # NOTE (VK): This unit test is added here because it results in a segmentation fault if
    # added to the test class below.
    @httpretty.activate
    @mock_course_catalog_api_client
    def test_omitting_unavailable_seats(self):
        """ Verify an unavailable seat is omitted from offer page results. """
        course1, seat1 = self.create_course_and_seat()
        course2, seat2 = self.create_course_and_seat()
        course_run_info = {
            'count': 2,
            'next': 'path/to/the/next/page',
            'results': [{
                'key': course1.id,
                'title': course1.name,
                'start': '2016-05-01T00:00:00Z',
                'image': {
                    'src': 'path/to/the/course/image'
                }
            }, {
                'key': course2.id,
                'title': course2.name,
                'start': '2016-05-01T00:00:00Z',
                'image': {
                    'src': 'path/to/the/course/image'
                }
            }]
        }

        self.mock_dynamic_catalog_course_runs_api(query='*:*', course_run_info=course_run_info)
        new_range, __ = Range.objects.get_or_create(catalog_query='*:*')
        new_range.add_product(seat1)
        new_range.add_product(seat2)
        voucher, __ = prepare_voucher(_range=new_range)
        voucher, products = get_voucher_and_products_from_code(voucher.code)
        factory = APIRequestFactory()
        request = factory.get('/?code={}&page_size=6'.format(voucher.code))
        request.site = self.site
        request.strategy = DefaultStrategy()
        offers = VoucherViewSet().get_offers(products=products, request=request, voucher=voucher)['results']
        self.assertEqual(len(offers), 2)

        products[1].expires = pytz.utc.localize(datetime.datetime.min)
        offers = VoucherViewSet().get_offers(products=products, request=request, voucher=voucher)['results']
        self.assertEqual(len(offers), 1)


@ddt.ddt
@httpretty.activate
class VoucherViewOffersEndpointTests(
        CourseCatalogMockMixin,
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
        request.strategy = DefaultStrategy()
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
        __, seat = self.create_course_and_seat()
        new_range = RangeFactory(products=[seat, ])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)

        with mock.patch(
            'ecommerce.extensions.api.v2.views.vouchers.VoucherViewSet.get_offers',
            mock.Mock(side_effect=exception)
        ):
            request = self.prepare_offers_listing_request(voucher.code)
            response = self.endpointView(request)

            self.assertEqual(response.status_code, 400)

    def test_get_offers_object_not_found(self):
        """ Verify the endpoint returns status 404 Not Found when product Course or Stock Record is not found """
        __, seat = self.create_course_and_seat()
        new_range = RangeFactory(products=[seat, ])
        voucher, __ = prepare_voucher(_range=new_range)

        with mock.patch(
            'ecommerce.extensions.api.v2.views.vouchers.VoucherViewSet.get_offers',
            mock.Mock(side_effect=Http404)
        ):
            request = self.prepare_offers_listing_request(voucher.code)
            response = self.endpointView(request)

            self.assertEqual(response.status_code, 404)

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
    @ddt.data(
        (
            StockRecord.objects.none(),
            'ecommerce.extensions.api.v2.views.vouchers.StockRecord.objects.filter'
        ),
        (
            Course.objects.none(),
            'ecommerce.extensions.api.v2.views.vouchers.Course.objects.filter'
        )
    )
    @ddt.unpack
    def test_voucher_offers_listing_catalog_query_exception(self, return_value, method):
        """
        Verify the endpoint returns status 200 and an empty list of course offers
        when all product Courses and Stock Records are not found
        and range has a catalog query
        """
        course, seat = self.create_course_and_seat()
        self.mock_dynamic_catalog_course_runs_api(query='*:*', course_run=course)
        new_range, __ = Range.objects.get_or_create(catalog_query='*:*')
        new_range.add_product(seat)
        voucher, __ = prepare_voucher(_range=new_range)
        voucher, products = get_voucher_and_products_from_code(voucher.code)
        request = self.prepare_offers_listing_request(voucher.code)

        with mock.patch(method, mock.Mock(return_value=return_value)):
            offers = VoucherViewSet().get_offers(products=products, request=request, voucher=voucher)['results']
            self.assertEqual(len(offers), 0)

    @mock_course_catalog_api_client
    def test_voucher_offers_listing_catalog_query(self):
        """ Verify the endpoint returns offers data for single product range. """
        course, seat = self.create_course_and_seat()
        self.mock_dynamic_catalog_course_runs_api(query='*:*', course_run=course)
        new_range, __ = Range.objects.get_or_create(catalog_query='*:*')
        new_range.add_product(seat)
        voucher, __ = prepare_voucher(_range=new_range)
        voucher, __ = get_voucher_and_products_from_code(voucher.code)
        request = self.prepare_offers_listing_request(voucher.code)
        response = self.endpointView(request)

        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)

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
        offers = VoucherViewSet().get_offers(products=products, request=request, voucher=voucher)['results']
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
            'image_url': get_lms_url('/asset-v1:test+test+test+type@asset+block@images_course_image.jpg'),
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
        offers = VoucherViewSet().get_offers(products=products, request=request, voucher=voucher)['results']
        first_offer = offers[0]

        self.assertEqual(len(offers), 1)
        self.assertDictEqual(first_offer, {
            'benefit': {
                'type': benefit.type,
                'value': benefit.value
            },
            'contains_verified': False,
            'course_start_date': '2016-05-01T00:00:00Z',
            'id': course.id,
            'image_url': 'path/to/the/course/image',
            'organization': CourseKey.from_string(course.id).org,
            'seat_type': course.type,
            'stockrecords': serializers.StockRecordSerializer(seat.stockrecords.first()).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime
        })

    def test_get_course_offer_data(self):
        """ Verify that the course offers data is properly formatted. """
        benefit = BenefitFactory()
        course, seat = self.create_course_and_seat()
        course_info = {
            'start': '2016-05-01T00:00:00Z',
            'image': {
                'src': 'path/to/the/course/image'
            }
        }
        stock_record = seat.stockrecords.first()
        voucher = VoucherFactory()

        offer = VoucherViewSet().get_course_offer_data(
            benefit=benefit,
            course=course,
            course_info=course_info,
            is_verified=True,
            stock_record=stock_record,
            voucher=voucher
        )

        self.assertDictEqual(offer, {
            'benefit': {
                'type': benefit.type,
                'value': benefit.value
            },
            'contains_verified': True,
            'course_start_date': course_info['start'],
            'id': course.id,
            'image_url': course_info['image']['src'],
            'organization': CourseKey.from_string(course.id).org,
            'seat_type': course.type,
            'stockrecords': serializers.StockRecordSerializer(stock_record).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime
        })
