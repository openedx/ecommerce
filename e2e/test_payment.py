from abc import ABCMeta
from unittest import skip, skipUnless

import ddt
from bok_choy.web_app_test import WebAppTest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from e2e.config import BULK_PURCHASE_SKU, MARKETING_URL_ROOT, PAYPAL_EMAIL, PAYPAL_PASSWORD, VERIFIED_COURSE_ID
from e2e.constants import ADDRESS_FR, ADDRESS_US
from e2e.mixins import EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin, PaymentMixin, UnenrollmentMixin
from e2e.pages.basket import BasketAddProductPage
from e2e.pages.lms import LMSCourseModePage
from e2e.pages.marketing import MarketingCourseAboutPage


class BasePaymentTest(UnenrollmentMixin, EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin, PaymentMixin,
                      WebAppTest):
    __metaclass__ = ABCMeta

    def setUp(self):
        super(BasePaymentTest, self).setUp()
        self.course_id = VERIFIED_COURSE_ID
        self.username, self.password, self.email = self.get_lms_user()
        self.basket_add_product_page = BasketAddProductPage(self.browser)


@ddt.ddt
class VerifiedCertificatePaymentTests(BasePaymentTest):
    def setUp(self):
        super(VerifiedCertificatePaymentTests, self).setUp()
        self.course_id = VERIFIED_COURSE_ID
        self.username, self.password, self.email = self.get_lms_user()
        self.basket_add_product_page = BasketAddProductPage(self.browser)

    def _start_checkout(self):
        """ Begin the checkout process for a verified certificate. """
        self.login_with_lms(self.email, self.password)

        if MARKETING_URL_ROOT:
            course_about_page = MarketingCourseAboutPage(self.browser, self.course_id)
            course_about_page.visit()

            # Click the first enroll button on the page to take the browser to the track selection page.
            course_about_page.q(css='.js-enroll-btn').first.click()

            # Wait for the track selection page to load.
            wait = WebDriverWait(self.browser, 10)
            track_selection_present = EC.presence_of_element_located((By.CLASS_NAME, 'form-register-choose'))
            wait.until(track_selection_present)
        else:
            course_modes_page = LMSCourseModePage(self.browser, self.course_id)
            course_modes_page.visit()

        # Click the purchase button on the track selection page to take the browser to the payment selection page.
        self.browser.find_element_by_css_selector('input[name=verified_mode]').click()

    @ddt.data(ADDRESS_US, ADDRESS_FR)
    def test_checkout_with_credit_card(self, address):
        """ Test the client-side checkout page.

        We use a U.S. address and a French address since the checkout page requires a state for the U.S. and
        Canada, but not for other countries.
        """
        self._start_checkout()
        self.checkout_with_credit_card(address)

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')

    @skip('See ECOM-7298.')
    def test_paypal(self):
        """ Test checkout with PayPal. """
        self._start_checkout()
        self.checkout_with_paypal()

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')


@ddt.ddt
@skipUnless(BULK_PURCHASE_SKU, 'A bulk purchase SKU must be provided to run bulk purchase tests!')
class BulkSeatPaymentTests(BasePaymentTest):
    def _start_bulk_seat_checkout(self):
        """ Begin the checkout process for a verified certificate. """
        self.login_with_lms(self.email, self.password)

        self.basket_add_product_page.visit()
        self.assertTrue(self.basket_add_product_page.is_browser_on_page())
        self.basket_add_product_page.update_product_quantity(5)

        # Click the purchase button on the track selection page to take
        # the browser to the payment selection page.
        self.browser.find_element_by_css_selector('button[id=paypal]').click()

    def test_bulk_seat_purchase_with_credit_card(self):
        """ Test bulk seat purchase checkout with CyberSource. """
        self._start_bulk_seat_checkout()
        self.browser.find_element_by_css_selector('button[id=cybersource]').click()
        self.checkout_with_credit_card(ADDRESS_US)

        self.assert_receipt_page_loads()
        self.assert_user_not_enrolled(self.username, self.course_id)

    def test_bulk_seat_purchase_with_paypal(self):
        """ Test bulk seat purchase checkout with PayPal. """
        if not (PAYPAL_EMAIL and PAYPAL_PASSWORD):
            self.fail('No PayPal credentials supplied!')

        self._start_bulk_seat_checkout()
        self.browser.find_element_by_css_selector('button[id=paypal]').click()
        self.checkout_with_paypal()

        self.assert_receipt_page_loads()
        self.assert_user_not_enrolled(self.username, self.course_id)
