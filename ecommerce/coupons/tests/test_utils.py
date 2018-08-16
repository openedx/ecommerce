import ddt
import httpretty
from edx_django_utils.cache import TieredCache
from mock import patch
from oscar.test.factories import ProductFactory, RangeFactory, VoucherFactory

from ecommerce.coupons.tests.mixins import DiscoveryMockMixin
from ecommerce.coupons.utils import fetch_course_catalog, is_voucher_applied, prepare_course_seat_types
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.testcases import TestCase


@ddt.ddt
@httpretty.activate
class CouponUtilsTests(TestCase, DiscoveryMockMixin):

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
