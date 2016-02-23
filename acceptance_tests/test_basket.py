from unittest import skipUnless

from bok_choy.web_app_test import WebAppTest

from acceptance_tests.config import ENABLE_OAUTH2_TESTS, VERIFIED_COURSE_ID
from acceptance_tests.mixins import (EcommerceApiMixin, EnrollmentApiMixin,
                                     LogistrationMixin, UnenrollmentMixin, PaymentMixin)
from acceptance_tests.pages import (BasketPage, CouponsCreateEditPage,
                                    CouponsDetailsPage, CouponsListPage,
                                    DashboardHomePage, RedeemVoucherPage)


@skipUnless(ENABLE_OAUTH2_TESTS, 'OAuth2 tests are not enabled.')
class BasketFlowTests(UnenrollmentMixin, EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin, WebAppTest,
                      PaymentMixin):
    def setUp(self):
        """ Instantiate the page objects. """
        super(BasketFlowTests, self).setUp()

        self.app_login_page = DashboardHomePage(self.browser)
        self.basket_page = BasketPage(self.browser)
        self.coupons_create_edit_page = CouponsCreateEditPage(self.browser)
        self.coupons_list_page = CouponsListPage(self.browser)
        self.coupons_details_page = CouponsDetailsPage(self.browser)
        self.redeem_voucher_page = RedeemVoucherPage(self.browser)

        self.course_id = VERIFIED_COURSE_ID
        self.username, self.password, self.email = self.get_lms_user()
        self.login_with_lms()

    def prepare_coupon(self, is_discount=False):
        """ Create a test coupon and open it's details page. """
        self.app_login_page.visit()
        self.assertTrue(self.app_login_page.is_browser_on_page())

        self.coupons_list_page.visit().create_new_coupon()
        self.coupons_create_edit_page.fill_create_coupon_form(is_discount)
        self.assertTrue(self.coupons_details_page.is_browser_on_page())

    def test_basket_flow_for_enrollment_code(self):
        """ Test redeeming an enrollment code enrolls the learner. """
        self.prepare_coupon()

        # Get the redeem URL for the coupon's detail page and go to it.
        redeem_url = self.coupons_details_page.get_redeem_url()
        self.browser.get(redeem_url)
        self.assertTrue(self.redeem_voucher_page.is_browser_on_page())

        # Click the 'Redeem and Enroll' button on the page.
        # The order should be completed and the user enrolled.
        self.redeem_voucher_page.proceed_to_enrollment()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, mode="verified")

    def test_basket_flow_for_discount_code(self):
        self.prepare_coupon(is_discount=True)

        redeem_url = self.coupons_details_page.get_redeem_url()
        self.browser.get(redeem_url)
        self.assertTrue(self.redeem_voucher_page.is_browser_on_page())

        self.redeem_voucher_page.proceed_to_checkout()
        self.assertTrue(self.basket_page.is_browser_on_page())
        self.checkout_with_paypal()

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')
