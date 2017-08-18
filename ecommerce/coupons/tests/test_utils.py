import ddt
from oscar.test.factories import ProductFactory, RangeFactory, VoucherFactory

from ecommerce.coupons.utils import is_voucher_applied, prepare_course_seat_types
from ecommerce.extensions.basket.utils import prepare_basket
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.testcases import TestCase


@ddt.ddt
class CouponAppViewTests(TestCase):

    def setUp(self):
        """
        Setup variables for test cases.
        """
        super(CouponAppViewTests, self).setUp()

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
