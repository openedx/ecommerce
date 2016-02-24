from unittest import skipUnless

import ddt
from bok_choy.web_app_test import WebAppTest

from acceptance_tests.config import ENABLE_OAUTH2_TESTS, VERIFIED_COURSE_ID, ENABLE_CYBERSOURCE_TESTS
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

    def start_redeem_flow(self, is_discount=False):
        """ Start redemption flow by creating a coupon via the UI and then accepting the offer """
        self.prepare_coupon()

        # Get the redeem URL for the coupon's detail page and go to it.
        redeem_url = self.coupons_details_page.get_redeem_url()
        self.browser.get(redeem_url)
        self.assertTrue(self.redeem_voucher_page.is_browser_on_page())

        if is_discount:
            self.redeem_voucher_page.proceed_to_checkout()
        else:
            self.redeem_voucher_page.proceed_to_enrollment()

    def prepare_coupon(self, is_discount=False):
        """ Create a test coupon and open it's details page. """
        self.app_login_page.visit()
        self.assertTrue(self.app_login_page.is_browser_on_page())

        self.coupons_list_page.visit().create_new_coupon()
        self.coupons_create_edit_page.fill_create_coupon_form(is_discount)
        self.assertTrue(self.coupons_details_page.is_browser_on_page())

    def test_basket_flow_for_enrollment_code(self):
        """ Test redeeming an enrollment code enrolls the learner. """
        self.start_redeem_flow()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, mode="verified")

    def test_paypal_basket_flow_for_discount_code(self):
        """ Test redemption of discount code and purchase of course via PayPal """
        self.start_redeem_flow(is_discount=True)
        self.assertTrue(self.basket_page.is_browser_on_page())
        self.checkout_with_paypal()

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')

    @skipUnless(ENABLE_CYBERSOURCE_TESTS, 'CyberSource tests are not enabled.')
    @ddt.data(
        {
            'country': 'US',
            'state': 'MA',
            'line1': '141 Portland Ave.',
            'line2': '9th Floor',
            'city': 'Cambridge',
            'postal_code': '02141',
        },
        {
            'country': 'FR',
            'state': None,
            'line1': 'Champ de Mars',
            'line2': '5 Avenue Anatole',
            'city': 'Paris',
            'postal_code': '75007',
        }
    )
    def test_cubersource_basket_flow_for_discount_code(self, address):
        """ Test redemption of discount code and purchase of course via Cybersource """
        self.start_redeem_flow(is_discount=True)
        self.assertTrue(self.basket_page.is_browser_on_page())
        self.checkout_with_cybersource(address)

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')
