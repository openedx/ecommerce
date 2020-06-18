

from datetime import datetime

import ddt
import httpretty
from edx_django_utils.cache import TieredCache
from mock import patch
from oscar.test.factories import ProductFactory, RangeFactory, VoucherFactory
from pytz import UTC

from ecommerce.coupons.tests.mixins import CouponMixin, DiscoveryMockMixin
from ecommerce.coupons.utils import (
    fetch_course_catalog,
    is_coupon_available,
    is_voucher_applied,
    prepare_course_seat_types,
    timezone
)
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.testcases import TestCase


@ddt.ddt
@httpretty.activate
class CouponUtilsTests(TestCase, CouponMixin, DiscoveryMockMixin):

    def setUp(self):
        """
        Setup variables for test cases.
        """
        super(CouponUtilsTests, self).setUp()

        self.user = self.create_user(email='test@tester.fake')
        self.request.user = self.user
        self.request.GET = {}

    @ddt.data(
        (['verIfiEd', 'profeSSional'], 'verified,professional'),
        (None, None)
    )
    @ddt.unpack
    def test_prepare_course_seat_types(self, course_seat_types, expected_result):
        """Verify prepare course seat types return correct value."""
        self.assertEqual(prepare_course_seat_types(course_seat_types), expected_result)

    def test_is_voucher_applied(self):
        """
        Verify is_voucher_applied return correct value.
        """
        product = ProductFactory(stockrecords__price_excl_tax=100)
        voucher, product = prepare_voucher(
            _range=RangeFactory(products=[product]),
            benefit_value=10
        )
        basket = prepare_basket(self.request, [product], voucher)

        # Verify is_voucher_applied returns True when voucher is applied to the basket.
        self.assertTrue(is_voucher_applied(basket, voucher))

        # Verify is_voucher_applied returns False when voucher can not be applied to the basket.
        self.assertFalse(is_voucher_applied(basket, VoucherFactory()))

    def test_fetch_course_catalog(self):
        """
        Verify that fetch_course_catalog is cached

        We expect 2 calls to set_all_tiers due to:
            - the site_configuration api setup
            - the result being cached
        """
        self.mock_access_token_response()
        self.mock_catalog_detail_endpoint(self.site_configuration.discovery_api_url)

        with patch.object(TieredCache, 'set_all_tiers', wraps=TieredCache.set_all_tiers) as mocked_set_all_tiers:
            mocked_set_all_tiers.assert_not_called()

            _ = fetch_course_catalog(self.site, 1)
            self.assertEqual(mocked_set_all_tiers.call_count, 2)

            _ = fetch_course_catalog(self.site, 1)
            self.assertEqual(mocked_set_all_tiers.call_count, 2)

    @ddt.data(
        {
            'start_datetime': datetime(2012, 11, 15, 1, 30, tzinfo=UTC),
            'end_datetime': datetime(2013, 7, 10, 6, 2, tzinfo=UTC),
            'timezone_now': datetime(2013, 1, 1, 1, 1, tzinfo=UTC),
            'coupon_available': True
        },
        {
            'start_datetime': datetime(2012, 11, 15, 1, 30, tzinfo=UTC),
            'end_datetime': datetime(2013, 7, 10, 6, 2, tzinfo=UTC),
            'timezone_now': datetime(2014, 1, 1, 1, 1, tzinfo=UTC),
            'coupon_available': False
        },
        {
            'start_datetime': datetime(2012, 11, 15, 1, 30, tzinfo=UTC),
            'end_datetime': datetime(2013, 7, 10, 6, 2, tzinfo=UTC),
            'timezone_now': datetime(2011, 1, 1, 1, 1, tzinfo=UTC),
            'coupon_available': False
        },
        {
            'start_datetime': datetime(2012, 11, 15, 1, 30, tzinfo=UTC),
            'end_datetime': datetime(2012, 11, 15, 1, 30, tzinfo=UTC),
            'timezone_now': datetime(2012, 11, 15, 1, 30, tzinfo=UTC),
            'coupon_available': False
        },
        {
            'start_datetime': datetime(2012, 11, 15, 1, 30, tzinfo=UTC),
            'end_datetime': datetime(2012, 11, 15, 1, 40, tzinfo=UTC),
            'timezone_now': datetime(2012, 11, 15, 1, 35, tzinfo=UTC),
            'coupon_available': True
        },
    )
    @ddt.unpack
    def test_is_coupon_available(self, start_datetime, end_datetime, timezone_now, coupon_available):
        """
        Verify `is_coupon_available` return correct value.
        """
        coupon = self.create_coupon(start_datetime=start_datetime, end_datetime=end_datetime)
        with patch.object(timezone, 'now', return_value=timezone_now):
            self.assertEqual(is_coupon_available(coupon), coupon_available)
