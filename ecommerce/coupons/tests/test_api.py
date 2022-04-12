import ddt
import httpretty
import mock
from django.utils.timezone import now, timedelta
from oscar.core.loading import get_class, get_model
from oscar.test.factories import BasketFactory, OrderFactory
from pytest import mark

from ecommerce.coupons.api import CouponCodeRedeemer, CustomEdxOrderPlacementMixin
from ecommerce.coupons.exceptions import RedeemCouponError
from ecommerce.coupons.tests.mixins import CouponMixin, DiscoveryMockMixin
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.catalogue.tests.mixins import DiscoveryTestMixin
from ecommerce.extensions.payment.models import EnterpriseContractMetadata
from ecommerce.extensions.test.factories import prepare_voucher
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.mixins import LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Applicator = get_class('offer.applicator', 'Applicator')
Basket = get_model('basket', 'Basket')
Benefit = get_model('offer', 'Benefit')
Catalog = get_model('catalogue', 'Catalog')
Course = get_model('courses', 'Course')
Product = get_model('catalogue', 'Product')
Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
OrderLineVouchers = get_model('voucher', 'OrderLineVouchers')
StockRecord = get_model('partner', 'StockRecord')
Voucher = get_model('voucher', 'Voucher')
VoucherApplication = get_model('voucher', 'VoucherApplication')
post_checkout = get_class('checkout.signals', 'post_checkout')

CONTENT_TYPE = 'application/json'
COUPON_CODE = 'COUPONTEST'
ENTERPRISE_CUSTOMER = 'cf246b88-d5f6-4908-a522-fc307e0b0c59'
ENTERPRISE_CUSTOMER_CATALOG = 'abc18838-adcb-41d5-abec-b28be5bfcc13'


@ddt.ddt
@mark.django_db
class CustomEdxOrderPlacemenMixinTests(TestCase):

    def setUp(self):
        super().setUp()

        class Stub(CustomEdxOrderPlacementMixin):
            def create_assignments_for_multi_use_per_customer(self, order):
                pass

            def update_assigned_voucher_offer_assignment(self, order):
                pass

        self.stub = Stub()

    def test_handle_successful_order(self):
        order = OrderFactory()
        order.basket = BasketFactory()
        order.user = UserFactory()

        with mock.patch.object(post_checkout, 'send', side_effect=post_checkout.send):
            self.stub.handle_successful_order(order)
            send_arguments = {
                'sender': mock.ANY,
                'order': order,
                'request': mock.ANY,
                'email_opt_in': False,
                'create_consent_record': False
            }
            post_checkout.send.assert_called_once_with(**send_arguments)


@ddt.ddt
@mark.django_db
class CouponCodeRedeemerTests(
        CouponMixin,
        DiscoveryTestMixin,
        LmsApiMockMixin,
        EnterpriseServiceMockMixin,
        TestCase,
        DiscoveryMockMixin):

    def setUp(self):
        super().setUp()

        self.user = self.create_user(email='test@tester.fake')
        self.course_1, self.seat_1 = self.create_course_and_seat(
            seat_type='verified',
            id_verification=True,
            price=50,
            partner=self.partner
        )
        self.course_2, self.seat_2 = self.create_course_and_seat(
            seat_type='professional',
            id_verification=True,
            price=0,
            partner=self.partner
        )
        self.stock_record_1 = StockRecord.objects.get(product=self.seat_1)
        self.stock_record_2 = StockRecord.objects.get(product=self.seat_2)
        self.catalog = Catalog.objects.create(partner=self.partner)
        self.catalog.stock_records.add(StockRecord.objects.get(product=self.seat_1))
        self.catalog.stock_records.add(StockRecord.objects.get(product=self.seat_2))

        self.coupon_code_redeemer = CouponCodeRedeemer(site=self.site)

        coupon_code, _ = self._create_coupon_and_get_code()
        self.coupon_code = coupon_code
        self.voucher = Voucher.objects.get(code=coupon_code)

        self.logger_patcher = mock.patch('ecommerce.coupons.api.logger')
        self.mock_logger = self.logger_patcher.start()

        self.get_course_detail_patcher = mock.patch('ecommerce.coupons.api.get_course_detail')
        self.mock_get_course_detail = self.get_course_detail_patcher.start()
        self.mock_get_course_detail.return_value = {
            'course_runs': [
                {
                    'seats': [
                        {
                            'type': 'verified',
                            'sku': self.stock_record_1.partner_sku
                        },
                        {
                            'type': 'professional',
                            'sku': self.stock_record_2.partner_sku
                        }
                    ]
                }
            ]
        }

        self.edx_rest_api_client_patcher = mock.patch('ecommerce.coupons.api.EdxRestApiClient')
        self.mock_edx_rest_api_client = self.edx_rest_api_client_patcher.start()
        self.mock_edx_rest_api_client().accounts.get.return_value = [{
            'is_active': True,
            'email': self.user.email
        }]

        self.addCleanup(self.logger_patcher.stop)
        self.addCleanup(self.mock_get_course_detail.stop)
        self.addCleanup(self.mock_edx_rest_api_client.stop)

    def _create_coupon_and_get_code(
            self,
            benefit_value=100,
            email_domains=None,
            enterprise_customer=ENTERPRISE_CUSTOMER,
            enterprise_customer_catalog=ENTERPRISE_CUSTOMER_CATALOG,
            course_id=None,
            catalog=None,
            contract_discount_value=None,
            contract_discount_type=EnterpriseContractMetadata.PERCENTAGE,
            prepaid_invoice_amount=None,
    ):
        """ Creates coupon and returns code. """
        coupon = self.create_coupon(
            benefit_value=benefit_value,
            catalog=catalog,
            email_domains=email_domains,
            enterprise_customer=enterprise_customer,
            enterprise_customer_catalog=enterprise_customer_catalog,
        )
        coupon.course_id = course_id
        if contract_discount_value is not None:
            ecm = EnterpriseContractMetadata.objects.create(
                discount_type=contract_discount_type,
                discount_value=contract_discount_value,
                amount_paid=prepaid_invoice_amount,
            )
            coupon.attr.enterprise_contract_metadata = ecm
        coupon.save()
        coupon_code = coupon.attr.coupon_vouchers.vouchers.first().code
        self.assertEqual(Voucher.objects.filter(code=coupon_code).count(), 1)
        return coupon_code, coupon

    def test_no_voucher(self):
        with self.assertRaises(RedeemCouponError):
            self.coupon_code_redeemer.redeem_coupon_code('code', 'edx+101', self.user.lms_user_id)

        assert self.mock_logger.exception.call_args[0][1] == 'No voucher found with code.'

    def test_inactive_voucher(self):
        self.voucher.start_datetime = now() + timedelta(days=1)
        self.voucher.save()
        with self.assertRaises(RedeemCouponError):
            self.coupon_code_redeemer.redeem_coupon_code(self.coupon_code, 'edx+101', self.user.lms_user_id)

        assert self.mock_logger.exception.call_args[0][1] == 'This coupon code is not active.'

    def test_used_voucher(self):
        order = OrderFactory()
        VoucherApplication.objects.create(voucher=self.voucher, user=self.user, order=order)

        with self.assertRaises(RedeemCouponError):
            self.coupon_code_redeemer.redeem_coupon_code(self.coupon_code, 'edx+101', self.user.lms_user_id)

        assert self.mock_logger.exception.call_args[0][1] == 'This coupon has already been used'

    def test_usage_exceeded_coupon(self):
        voucher, _ = prepare_voucher(usage=Voucher.ONCE_PER_CUSTOMER, max_usage=1)
        voucher.offers.first().record_usage(discount={'freq': 1, 'discount': 1})
        with self.assertRaises(RedeemCouponError):
            self.coupon_code_redeemer.redeem_coupon_code(voucher.code, 'edx+101', self.user.lms_user_id)

        assert self.mock_logger.exception.call_args[0][1] == 'This coupon code is no longer available.'

    @httpretty.activate
    def test_invalid_email_domain(self):
        self.mock_access_token_response()

        coupon_code, _ = self._create_coupon_and_get_code(email_domains='abc.com')
        with self.assertRaises(RedeemCouponError):
            self.coupon_code_redeemer.redeem_coupon_code(coupon_code, 'edx+101', self.user.lms_user_id)

        assert self.mock_logger.exception.call_args[0][1] == 'User email does not meet domain requirements.'

    @httpretty.activate
    def test_user_not_active(self):
        self.mock_access_token_response()
        self.mock_edx_rest_api_client().accounts.get.return_value = [{
            'is_active': False,
            'email': self.user.email
        }]

        with self.assertRaises(RedeemCouponError):
            self.coupon_code_redeemer.redeem_coupon_code(self.coupon_code, 'edx+101', self.user.lms_user_id)

        assert self.mock_logger.exception.call_args[0][1] == 'User is not active.'

    def test_no_stock_record(self):
        self.mock_get_course_detail.return_value = {
            'course_runs': [
                {
                    'seats': [
                        {
                            'type': 'verified',
                            'sku': 'abc'
                        }
                    ]
                }
            ]
        }

        with self.assertRaises(RedeemCouponError):
            self.coupon_code_redeemer.redeem_coupon_code(self.coupon_code, 'edx+101', self.user.lms_user_id)

        assert self.mock_logger.exception.call_args[0][1] == 'Product does not exist.'

    @httpretty.activate
    def test_successful_redemption(self):
        self.mock_assignable_enterprise_condition_calls(ENTERPRISE_CUSTOMER_CATALOG)
        self.mock_specific_enterprise_customer_api(ENTERPRISE_CUSTOMER)

        self.coupon_code_redeemer.redeem_coupon_code(self.coupon_code, 'edx+101', self.user.lms_user_id)

        assert self.mock_logger.info.call_args[0][0] == 'Code %s successfully redeemed for user %s for course %s.'
