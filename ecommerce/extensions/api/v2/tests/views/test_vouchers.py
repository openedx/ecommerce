

import datetime
from uuid import uuid4

import ddt
import httpretty
import mock
import pytz
from django.http import Http404
from django.urls import reverse
from django.utils.timezone import now
from opaque_keys.edx.keys import CourseKey
from oscar.core.loading import get_model
from oscar.test.factories import BenefitFactory, OrderFactory, OrderLineFactory, ProductFactory, RangeFactory
from requests.exceptions import ConnectionError as ReqConnectionError
from requests.exceptions import Timeout
from rest_framework import status
from rest_framework.test import APIRequestFactory
from slumber.exceptions import SlumberBaseException

from ecommerce.coupons.tests.mixins import CouponMixin, DiscoveryMockMixin
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.api import serializers
from ecommerce.extensions.api.v2.views.vouchers import VoucherViewSet
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.offer.utils import get_benefit_type
from ecommerce.extensions.partner.strategy import DefaultStrategy
from ecommerce.extensions.test.factories import (
    ConditionalOfferFactory,
    VoucherFactory,
    prepare_enterprise_voucher,
    prepare_voucher
)
from ecommerce.extensions.voucher.models import CouponVouchers
from ecommerce.tests.factories import PartnerFactory
from ecommerce.tests.mixins import Catalog, LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Product = get_model('catalogue', 'Product')
Range = get_model('offer', 'Range')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')


@ddt.ddt
class VoucherViewSetTests(DiscoveryMockMixin, DiscoveryTestMixin, LmsApiMockMixin, TestCase):
    """ Tests for the VoucherViewSet view set. """
    path = reverse('api:v2:vouchers-list')

    def setUp(self):
        super(VoucherViewSetTests, self).setUp()
        self.user = self.create_user(is_staff=True)
        self.client.login(username=self.user.username, password=self.password)

    def create_vouchers(self, partner=None, count=1):
        """Helper function that creates vouchers with a mocked coupon relation."""
        vouchers = VoucherFactory.create_batch(count)
        partner = partner or self.partner
        coupon_vouchers = CouponVouchers.objects.create(
            coupon=ProductFactory(stockrecords__partner=partner)
        )
        for voucher in vouchers:
            voucher.offers.add(ConditionalOfferFactory())
            coupon_vouchers.vouchers.add(voucher)
        return vouchers

    def test_list(self):
        """ Verify the endpoint lists all vouchers. """
        vouchers = self.create_vouchers(count=3)
        self.create_vouchers(partner=PartnerFactory())
        response = self.client.get(self.path)
        self.assertEqual(Voucher.objects.count(), 4)
        self.assertEqual(response.data['count'], len(vouchers))

        actual_codes = [datum['code'] for datum in response.data['results']]
        expected_codes = [voucher.code for voucher in vouchers]
        self.assertEqual(actual_codes, expected_codes)

    def test_list_with_code_filter(self):
        """ Verify the endpoint list all vouchers, filtered by the specified code. """
        voucher = self.create_vouchers()[0]

        url = '{path}?code={code}'.format(path=self.path, code=voucher.code)
        response = self.client.get(url)

        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['code'], voucher.code)

    def prepare_get_offers_response(self, quantity=1, seat_type='verified', seats=None):
        """Helper method for creating response the voucher offers endpoint.

        Args:
            quantity (int): Number of course runs

        Returns:
            The products, request and vouchers created.
        """
        course_run_info = {
            'count': quantity,
            'next': 'path/to/the/next/page',
            'results': []
        }
        products = []
        new_range, __ = Range.objects.get_or_create(catalog_query='*:*', course_seat_types=seat_type)
        if seats:
            for seat in seats:
                course_run_info['results'].append({
                    'image': {
                        'src': 'path/to/the/course/image'
                    },
                    'key': seat.course_id,
                    'start': '2016-05-01T00:00:00Z',
                    'enrollment_start': '2016-05-01T00:00:00Z',
                    'title': seat.title,
                    'enrollment_end': None
                })
                new_range.add_product(seat)
        else:
            for _ in range(quantity):
                course, seat = self.create_course_and_seat(seat_type=seat_type)
                course_run_info['results'].append({
                    'image': {
                        'src': 'path/to/the/course/image'
                    },
                    'key': course.id,
                    'start': '2016-05-01T00:00:00Z',
                    'enrollment_start': '2016-05-01T00:00:00Z',
                    'title': course.name,
                    'enrollment_end': None
                })
                new_range.add_product(seat)
                products.append(seat)

        self.mock_course_runs_endpoint(
            self.site_configuration.discovery_api_url, query='*:*', course_run_info=course_run_info
        )
        voucher, __ = prepare_voucher(_range=new_range)

        factory = APIRequestFactory()
        request = factory.get('/?code={}&page_size=6'.format(voucher.code))
        request.site = self.site
        request.user = self.user
        request.strategy = DefaultStrategy()

        return products, request, voucher

    def build_offers_url(self, voucher):
        return '{path}?code={code}'.format(path=reverse('api:v2:vouchers-offers'), code=voucher.code)

    @httpretty.activate
    def test_omitting_unavailable_seats(self):
        """ Verify an unavailable seat is omitted from offer page results. """
        self.mock_access_token_response()
        products, request, voucher = self.prepare_get_offers_response(quantity=2)
        url = self.build_offers_url(voucher)

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 2)

        product = products[0]
        product.expires = pytz.utc.localize(datetime.datetime.min)
        product.save()

        offers = VoucherViewSet().get_offers(request=request, voucher=voucher)['results']
        self.assertEqual(len(offers), 1)

    @httpretty.activate
    def test_omitting_already_bought_credit_seat(self):
        """ Verify a seat that the user bought is omitted from offer page results. """
        self.mock_access_token_response()
        products, request, voucher = self.prepare_get_offers_response(quantity=2, seat_type='credit')
        self.mock_eligibility_api(request, self.user, 'a/b/c', eligible=True)
        offers = VoucherViewSet().get_offers(request=request, voucher=voucher)['results']
        self.assertEqual(len(offers), 2)

        order = OrderFactory(user=self.user)
        order.lines.add(OrderLineFactory(product=products[0], partner_sku='test_sku'))
        offers = VoucherViewSet().get_offers(request=request, voucher=voucher)['results']
        self.assertEqual(len(offers), 1)

    @httpretty.activate
    @ddt.data((1, True), (0, False))
    @ddt.unpack
    def test_omitting_uneligible_credit_seat(self, offer_num, eligible):
        """ Verify a seat that the user is not eligible for is omitted from offer page results. """
        self.mock_access_token_response()
        products, request, voucher = self.prepare_get_offers_response(quantity=1, seat_type='credit')
        self.mock_eligibility_api(request, self.user, products[0].attr.course_key, eligible=eligible)
        offers = VoucherViewSet().get_offers(request=request, voucher=voucher)['results']
        self.assertEqual(len(offers), offer_num)

    @httpretty.activate
    def test_multiple_providers(self):
        """ Verify offer contains information about credit providers. """
        course = CourseFactory(partner=self.partner)
        seat1 = course.create_or_update_seat(
            'credit', False, 100, credit_provider='test_provider_1'
        )
        seat2 = course.create_or_update_seat(
            'credit', False, 100, credit_provider='test_provider_2'
        )
        self.assertEqual(Product.objects.filter(parent=seat1.parent).count(), 2)

        self.mock_access_token_response()
        __, request, voucher = self.prepare_get_offers_response(seats=[seat1, seat2], seat_type='credit')
        self.mock_eligibility_api(request, self.user, course.id)
        offers = VoucherViewSet().get_offers(request=request, voucher=voucher)['results']
        for offer in offers:
            self.assertTrue(offer['multiple_credit_providers'])
            self.assertIsNone(offer['credit_provider_price'])

    def test_omitting_expired_courses(self):
        """Verify professional courses who's enrollment end datetime have passed are omitted."""
        no_enrollment_end_seat = CourseFactory(partner=self.partner).create_or_update_seat('professional', False, 100)
        no_enrollment_start_seat = CourseFactory(partner=self.partner).create_or_update_seat('professional', False, 100)
        valid_seat = CourseFactory(partner=self.partner).create_or_update_seat('professional', False, 100)
        expired_enrollment_seat = CourseFactory(partner=self.partner).create_or_update_seat('professional', False, 100)
        expired_seat = CourseFactory(partner=self.partner).create_or_update_seat('professional', False, 100)
        future_enrollment_seat = CourseFactory(partner=self.partner).create_or_update_seat('professional', False, 100)

        course_discovery_results = [
            {
                'key': no_enrollment_end_seat.attr.course_key,
                'enrollment_end': None,
                'enrollment_start': str(now() - datetime.timedelta(days=1)),
            },
            {
                'key': no_enrollment_start_seat.attr.course_key,
                'enrollment_start': None,
                'enrollment_end': None,
            },
            {
                'key': valid_seat.attr.course_key,
                'enrollment_end': str(now() + datetime.timedelta(days=1)),
                'enrollment_start': str(now() - datetime.timedelta(days=1)),
            },
            {
                'key': expired_enrollment_seat.attr.course_key,
                'enrollment_end': str(now() - datetime.timedelta(days=1)),
                'enrollment_start': str(now() - datetime.timedelta(days=1)),
            },
            {
                'key': expired_seat.attr.course_key,
                'enrollment_end': None,
                'enrollment_start': str(now() - datetime.timedelta(days=1)),
                'end': str(now() - datetime.timedelta(days=1)),
            },
            {
                'key': future_enrollment_seat.attr.course_key,
                'enrollment_end': None,
                'enrollment_start': str(now() + datetime.timedelta(days=1)),
            }
        ]

        products, _, __ = VoucherViewSet().retrieve_course_objects(course_discovery_results, 'professional')
        self.assertIn(no_enrollment_end_seat, products)
        self.assertIn(no_enrollment_start_seat, products)
        self.assertIn(valid_seat, products)
        self.assertNotIn(expired_enrollment_seat, products)
        self.assertNotIn(expired_seat, products)
        self.assertNotIn(future_enrollment_seat, products)


@ddt.ddt
@httpretty.activate
class VoucherViewOffersEndpointTests(DiscoveryMockMixin, CouponMixin, DiscoveryTestMixin, LmsApiMockMixin,
                                     TestCase):
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
        self.mock_access_token_response()
        course, seat = self.create_course_and_seat()
        self.mock_course_run_detail_endpoint(
            course, discovery_api_url=self.site_configuration.discovery_api_url
        )
        new_range = RangeFactory(products=[seat, ])
        new_range.catalog = Catalog.objects.create(partner=self.partner)
        new_range.catalog.stock_records.add(StockRecord.objects.get(product=seat))
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        request = self.prepare_offers_listing_request(voucher.code)
        response = self.endpointView(request)
        self.assertEqual(response.status_code, 200)

        new_range.remove_product(seat)
        response = self.endpointView(request)
        self.assertEqual(response.status_code, 404)

    @ddt.data((ReqConnectionError,), (Timeout,), (SlumberBaseException,))
    @ddt.unpack
    def test_voucher_offers_listing_api_exception_caught(self, exception):
        """ Verify the endpoint returns status 400 Bad Request when ConnectionError occurs """
        __, seat = self.create_course_and_seat()
        new_range = RangeFactory(products=[seat, ])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)

        with mock.patch(
                'ecommerce.extensions.api.v2.views.vouchers.VoucherViewSet.get_offers',
                mock.Mock(side_effect=exception)):
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
                mock.Mock(side_effect=Http404)):
            request = self.prepare_offers_listing_request(voucher.code)
            response = self.endpointView(request)

            self.assertEqual(response.status_code, 404)

    def test_voucher_offers_listing_product_found(self):
        """ Verify the endpoint returns offers data for single product range. """
        self.mock_access_token_response()
        course, seat = self.create_course_and_seat()
        self.mock_course_run_detail_endpoint(
            course, discovery_api_url=self.site_configuration.discovery_api_url
        )

        new_range = RangeFactory(products=[seat, ])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        request = self.prepare_offers_listing_request(voucher.code)
        response = self.endpointView(request)

        self.assertEqual(response.status_code, 200)

    @ddt.data(
        (
            StockRecord.objects.none(),
            'ecommerce.extensions.api.v2.views.vouchers.StockRecord.objects.filter'
        ),
        (
            Product.objects.none(),
            'ecommerce.extensions.api.v2.views.vouchers.Product.objects.filter'
        )
    )
    @ddt.unpack
    def test_voucher_offers_listing_catalog_query_exception(self, return_value, method):
        """
        Verify the endpoint returns status 200 and an empty list of course offers
        when all product Courses and Stock Records are not found
        and range has a catalog query
        """
        self.mock_access_token_response()
        course, seat = self.create_course_and_seat()
        self.mock_course_runs_endpoint(
            self.site_configuration.discovery_api_url, query='*:*', course_run=course
        )
        new_range, __ = Range.objects.get_or_create(catalog_query='*:*', course_seat_types='verified')
        new_range.add_product(seat)
        voucher, __ = prepare_voucher(_range=new_range)
        request = self.prepare_offers_listing_request(voucher.code)

        with mock.patch(method, mock.Mock(return_value=return_value)):
            offers = VoucherViewSet().get_offers(request=request, voucher=voucher)['results']
            self.assertEqual(len(offers), 0)

    def test_voucher_offers_listing_catalog_query(self):
        """ Verify the endpoint returns offers data for single product range. """
        self.mock_access_token_response()
        course, seat = self.create_course_and_seat()
        self.mock_course_runs_endpoint(
            self.site_configuration.discovery_api_url, query='*:*', course_run=course
        )
        new_range, __ = Range.objects.get_or_create(catalog_query='*:*', course_seat_types='verified')
        new_range.add_product(seat)
        voucher, __ = prepare_voucher(_range=new_range)
        request = self.prepare_offers_listing_request(voucher.code)
        response = self.endpointView(request)

        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)

    def test_get_offers_for_single_course_voucher(self):
        """ Verify that the course offers data is returned for a single course voucher. """
        self.mock_access_token_response()
        course, seat = self.create_course_and_seat()
        new_range = RangeFactory(products=[seat, ])
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        benefit = voucher.offers.first().benefit
        request = self.prepare_offers_listing_request(voucher.code)
        self.mock_course_run_detail_endpoint(
            course, discovery_api_url=self.site_configuration.discovery_api_url
        )
        offers = VoucherViewSet().get_offers(request=request, voucher=voucher)['results']
        first_offer = offers[0]

        self.assertEqual(len(offers), 1)
        self.assertDictEqual(first_offer, {
            'benefit': {
                'type': get_benefit_type(benefit),
                'value': benefit.value
            },
            'contains_verified': True,
            'course_start_date': '2013-02-05T05:00:00Z',
            'id': course.id,
            'image_url': '/path/to/image.jpg',
            'multiple_credit_providers': False,
            'organization': CourseKey.from_string(course.id).org,
            'credit_provider_price': None,
            'seat_type': seat.attr.certificate_type,
            'stockrecords': serializers.StockRecordSerializer(seat.stockrecords.first()).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime,
        })

    def test_get_offers_for_multiple_courses_voucher(self):
        """ Verify that the course offers data is returned for a multiple courses voucher. """
        self.mock_access_token_response()
        course, seat = self.create_course_and_seat()
        self.mock_course_runs_endpoint(
            self.site_configuration.discovery_api_url, query='*:*', course_run=course
        )
        new_range, __ = Range.objects.get_or_create(catalog_query='*:*', course_seat_types='verified')
        new_range.add_product(seat)
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        benefit = voucher.offers.first().benefit
        request = self.prepare_offers_listing_request(voucher.code)
        offers = VoucherViewSet().get_offers(request=request, voucher=voucher)['results']
        first_offer = offers[0]
        self.assertEqual(len(offers), 1)
        self.assertDictEqual(first_offer, {
            'benefit': {
                'type': get_benefit_type(benefit),
                'value': benefit.value
            },
            'contains_verified': True,
            'course_start_date': '2016-05-01T00:00:00Z',
            'id': course.id,
            'image_url': 'path/to/the/course/image',
            'multiple_credit_providers': False,
            'organization': CourseKey.from_string(course.id).org,
            'credit_provider_price': None,
            'seat_type': seat.attr.certificate_type,
            'stockrecords': serializers.StockRecordSerializer(seat.stockrecords.first()).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime,
        })

    def test_get_offers_for_enterprise_catalog_voucher(self):
        """ Verify that the course offers data is returned for an enterprise catalog voucher. """
        self.mock_access_token_response()
        course, seat = self.create_course_and_seat()
        enterprise_catalog_id = str(uuid4())
        self.mock_enterprise_catalog_course_endpoint(
            self.site_configuration.enterprise_api_url, enterprise_catalog_id, course_run=course
        )
        new_range, __ = Range.objects.get_or_create(
            catalog_query='*:*',
            course_seat_types='verified',
            enterprise_customer=str(uuid4()),
            enterprise_customer_catalog=enterprise_catalog_id,
        )
        new_range.add_product(seat)
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)
        benefit = voucher.offers.first().benefit
        request = self.prepare_offers_listing_request(voucher.code)
        offers = VoucherViewSet().get_offers(request=request, voucher=voucher)['results']
        first_offer = offers[0]
        self.assertEqual(len(offers), 1)
        self.assertDictEqual(first_offer, {
            'benefit': {
                'type': get_benefit_type(benefit),
                'value': benefit.value
            },
            'contains_verified': True,
            'course_start_date': '2016-05-01T00:00:00Z',
            'id': course.id,
            'image_url': 'path/to/the/course/image',
            'multiple_credit_providers': False,
            'organization': CourseKey.from_string(course.id).org,
            'credit_provider_price': None,
            'seat_type': seat.attr.certificate_type,
            'stockrecords': serializers.StockRecordSerializer(seat.stockrecords.first()).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime,
        })

    def test_get_offers_for_enterprise_offer(self):
        """ Verify that the course offers data is returned for an enterprise catalog voucher. """
        self.mock_access_token_response()
        course, seat = self.create_course_and_seat()
        enterprise_customer_id = str(uuid4())
        enterprise_catalog_id = str(uuid4())
        self.mock_enterprise_catalog_course_endpoint(
            self.site_configuration.enterprise_api_url, enterprise_catalog_id, course_run=course
        )
        voucher = prepare_enterprise_voucher(
            benefit_value=10,
            enterprise_customer=enterprise_customer_id,
            enterprise_customer_catalog=enterprise_catalog_id
        )
        benefit = voucher.offers.first().benefit
        request = self.prepare_offers_listing_request(voucher.code)
        offers = VoucherViewSet().get_offers(request=request, voucher=voucher)['results']
        first_offer = offers[0]
        self.assertEqual(len(offers), 1)
        self.assertDictEqual(first_offer, {
            'benefit': {
                'type': get_benefit_type(benefit),
                'value': benefit.value
            },
            'contains_verified': True,
            'course_start_date': '2016-05-01T00:00:00Z',
            'id': course.id,
            'image_url': 'path/to/the/course/image',
            'multiple_credit_providers': False,
            'organization': CourseKey.from_string(course.id).org,
            'credit_provider_price': None,
            'seat_type': seat.attr.certificate_type,
            'stockrecords': serializers.StockRecordSerializer(seat.stockrecords.first()).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime,
        })

    def test_get_offers_for_enterprise_offer_no_catalog(self):
        """ Verify that the course offers data is returned for an enterprise catalog voucher. """
        self.mock_access_token_response()
        enterprise_customer_id = str(uuid4())
        voucher = prepare_enterprise_voucher(
            benefit_value=10,
            enterprise_customer=enterprise_customer_id,
        )
        request = self.prepare_offers_listing_request(voucher.code)
        offers = VoucherViewSet().get_offers(request=request, voucher=voucher)['results']
        self.assertEqual(len(offers), 0)

    def test_get_offers_for_course_catalog_voucher(self):
        """ Verify that the course offers data is returned for a course catalog voucher. """
        catalog_id = 1
        catalog_query = '*:*'

        self.mock_access_token_response()
        # Populate database for the test case.
        course, seat = self.create_course_and_seat()
        new_range, __ = Range.objects.get_or_create(course_catalog=catalog_id, course_seat_types='verified')
        new_range.add_product(seat)
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)

        # Mock network calls
        self.mock_course_runs_endpoint(
            query=catalog_query, course_run=course, discovery_api_url=self.site_configuration.discovery_api_url
        )
        self.mock_catalog_detail_endpoint(
            catalog_id=catalog_id, expected_query=catalog_query,
            discovery_api_url=self.site_configuration.discovery_api_url
        )

        benefit = voucher.offers.first().benefit
        request = self.prepare_offers_listing_request(voucher.code)
        offers = VoucherViewSet().get_offers(request=request, voucher=voucher)['results']
        first_offer = offers[0]

        # Verify that offers are returned when voucher is created using course catalog
        self.assertEqual(len(offers), 1)
        self.assertDictEqual(first_offer, {
            'benefit': {
                'type': get_benefit_type(benefit),
                'value': benefit.value
            },
            'contains_verified': True,
            'course_start_date': '2016-05-01T00:00:00Z',
            'id': course.id,
            'image_url': 'path/to/the/course/image',
            'multiple_credit_providers': False,
            'organization': CourseKey.from_string(course.id).org,
            'credit_provider_price': None,
            'seat_type': seat.attr.certificate_type,
            'stockrecords': serializers.StockRecordSerializer(seat.stockrecords.first()).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime,
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
            credit_provider_price=None,
            multiple_credit_providers=False,
            is_verified=True,
            product=seat,
            stock_record=stock_record,
            voucher=voucher
        )

        self.assertDictEqual(offer, {
            'benefit': {
                'type': get_benefit_type(benefit),
                'value': benefit.value
            },
            'contains_verified': True,
            'course_start_date': course_info['start'],
            'id': course.id,
            'image_url': course_info['image']['src'],
            'multiple_credit_providers': False,
            'organization': CourseKey.from_string(course.id).org,
            'credit_provider_price': None,
            'seat_type': seat.attr.certificate_type,
            'stockrecords': serializers.StockRecordSerializer(stock_record).data,
            'title': course.name,
            'voucher_end_date': voucher.end_datetime,
        })

    def test_get_course_offer_verify_null_fields(self):
        """ Verify that the course offers data is properly formatted. """
        benefit = BenefitFactory()
        course, seat = self.create_course_and_seat()
        course_info = {
            'start': None,
            'image': None,
        }
        stock_record = seat.stockrecords.first()
        voucher = VoucherFactory()
        offer = VoucherViewSet().get_course_offer_data(
            benefit=benefit,
            course=course,
            course_info=course_info,
            credit_provider_price=None,
            is_verified=True,
            multiple_credit_providers=False,
            product=seat,
            stock_record=stock_record,
            voucher=voucher
        )

        self.assertEqual(offer['image_url'], '')
        self.assertEqual(offer['course_start_date'], None)

    def test_offers_api_endpoint_for_course_catalog_voucher(self):
        """
        Verify that the course offers data is returned for a course catalog voucher.
        """
        catalog_id = 1
        catalog_query = '*:*'

        self.mock_access_token_response()
        # Populate database for the test case.
        course, seat = self.create_course_and_seat()
        new_range, __ = Range.objects.get_or_create(course_catalog=catalog_id, course_seat_types='verified')
        new_range.add_product(seat)
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)

        # Mock network calls
        self.mock_catalog_detail_endpoint(
            catalog_id=catalog_id, expected_query=catalog_query,
            discovery_api_url=self.site_configuration.discovery_api_url
        )
        self.mock_course_runs_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, query=catalog_query, course_run=course
        )

        benefit = voucher.offers.first().benefit
        request = self.prepare_offers_listing_request(voucher.code)

        response = self.endpointView(request)
        # Verify that offers are returned when voucher is created using course catalog
        self.assertEqual(response.status_code, 200)
        self.assertListEqual(
            response.data['results'],
            [{
                'benefit': {
                    'type': get_benefit_type(benefit),
                    'value': benefit.value
                },
                'contains_verified': True,
                'course_start_date': '2016-05-01T00:00:00Z',
                'id': course.id,
                'image_url': 'path/to/the/course/image',
                'multiple_credit_providers': False,
                'organization': CourseKey.from_string(course.id).org,
                'credit_provider_price': None,
                'seat_type': seat.attr.certificate_type,
                'stockrecords': serializers.StockRecordSerializer(seat.stockrecords.first()).data,
                'title': course.name,
                'voucher_end_date': voucher.end_datetime,
            }],
        )

    def test_get_offers_for_course_catalog_voucher_api_error(self):
        """
        Verify that offers api endpoint returns proper message if Discovery Service API returns error.
        """
        catalog_id = 1
        catalog_query = '*:*'

        self.mock_access_token_response()
        # Populate database for the test case.
        course, seat = self.create_course_and_seat()
        new_range, __ = Range.objects.get_or_create(course_catalog=catalog_id, course_seat_types='verified')
        new_range.add_product(seat)
        voucher, __ = prepare_voucher(_range=new_range, benefit_value=10)

        # Mock network calls
        self.mock_catalog_detail_endpoint(
            catalog_id=catalog_id, expected_query=catalog_query,
            discovery_api_url=self.site_configuration.discovery_api_url, expected_status=status.HTTP_404_NOT_FOUND
        )
        self.mock_course_runs_endpoint(
            discovery_api_url=self.site_configuration.discovery_api_url, query=catalog_query, course_run=course
        )

        request = self.prepare_offers_listing_request(voucher.code)
        response = self.endpointView(request)
        # Verify that offers are returned when voucher is created using course catalog
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
