import ddt
from bok_choy.web_app_test import WebAppTest

from e2e.config import VERIFIED_COURSE_ID
from e2e.constants import ADDRESS_FR, ADDRESS_US, CODE
from e2e.mixins import (
    CouponMixin, EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin, PaymentMixin, UnenrollmentMixin
)
from e2e.pages.basket import BasketPage
from e2e.pages.coupons import CouponsCreatePage, CouponsDetailsPage, CouponsListPage, RedeemVoucherPage
from e2e.pages.ecommerce import EcommerceDashboardHomePage


@ddt.ddt
class CouponCheckoutTests(CouponMixin, UnenrollmentMixin, EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin,
                          PaymentMixin, WebAppTest):
    def setUp(self):
        """ Instantiate the page objects. """
        super(CouponCheckoutTests, self).setUp()

        self.app_login_page = EcommerceDashboardHomePage(self.browser)
        self.basket_page = BasketPage(self.browser)
        self.coupons_create_edit_page = CouponsCreatePage(self.browser)
        self.coupons_list_page = CouponsListPage(self.browser)
        self.coupons_details_page = CouponsDetailsPage(self.browser)
        self.redeem_voucher_page = RedeemVoucherPage(self.browser)

        self.course_id = VERIFIED_COURSE_ID
        self.username, self.password, self.email = self.get_lms_user()
        self.login_with_lms()

    def start_redeem_flow(self, is_discount=False):
        """ Start redemption flow by creating a coupon via the UI and then accepting the offer """
        self.prepare_coupon(is_discount)

        # Get the redeem URL for the coupon's detail page and go to it.
        redeem_url = self.coupons_details_page.get_redeem_url(CODE)
        self.browser.get(redeem_url)
        self.assertTrue(self.redeem_voucher_page.is_browser_on_page())

        if is_discount:
            self.redeem_voucher_page.proceed_to_checkout()
        else:
            self.redeem_voucher_page.proceed_to_enrollment()

    def prepare_coupon(self, is_discount=False):
        """ Create a test coupon and open its details page. """
        self.app_login_page.visit()
        self.assertTrue(self.app_login_page.is_browser_on_page())

        self.coupons_list_page.visit().create_new_coupon()
        self.coupons_create_edit_page.fill_create_coupon_form(is_discount)
        self.assertTrue(self.coupons_details_page.is_browser_on_page())

    def test_enrollment_code_redemption(self):
        """ Test redeeming an enrollment code enrolls the learner. """
        self.start_redeem_flow()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, mode='verified')

    def test_discount_checkout_with_paypal(self):
        """ Test redemption of discount code and purchase of course via PayPal """
        self.start_redeem_flow(is_discount=True)
        self.assertTrue(self.basket_page.is_browser_on_page())
        self.checkout_with_paypal()

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')

    @ddt.data(ADDRESS_US, ADDRESS_FR)
    def test_discount_checkout_with_cybersource(self, address):
        """ Test redemption of discount code and purchase of course via Cybersource """
        self.start_redeem_flow(is_discount=True)
        self.assertTrue(self.basket_page.is_browser_on_page())
        self.checkout_with_cybersource(address)

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')
