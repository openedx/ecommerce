from unittest import skipUnless

from bok_choy.web_app_test import WebAppTest
import ddt
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from acceptance_tests.config import (VERIFIED_COURSE_ID, MARKETING_URL_ROOT,
                                     PAYPAL_PASSWORD, PAYPAL_EMAIL, ENABLE_CYBERSOURCE_TESTS)
from acceptance_tests.constants import CYBERSOURCE_DATA1, CYBERSOURCE_DATA2
from acceptance_tests.mixins import (LogistrationMixin, EnrollmentApiMixin, EcommerceApiMixin,
                                     PaymentMixin, UnenrollmentMixin)
from acceptance_tests.pages import LMSCourseModePage, MarketingCourseAboutPage


@ddt.ddt
class VerifiedCertificatePaymentTests(UnenrollmentMixin, EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin,
                                      PaymentMixin, WebAppTest):
    def setUp(self):
        super(VerifiedCertificatePaymentTests, self).setUp()
        self.course_id = VERIFIED_COURSE_ID
        self.username, self.password, self.email = self.get_lms_user()

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

        # Click the purchase button on the track selection page to take
        # the browser to the payment selection page.
        self.browser.find_element_by_css_selector('input[name=verified_mode]').click()

    @skipUnless(ENABLE_CYBERSOURCE_TESTS, 'CyberSource tests are not enabled.')
    @ddt.data(CYBERSOURCE_DATA1, CYBERSOURCE_DATA2)
    def test_cybersource(self, address):
        """ Test checkout with CyberSource. """
        self._start_checkout()
        self.checkout_with_cybersource(address)

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')

    def test_paypal(self):
        """ Test checkout with PayPal. """
        if not (PAYPAL_EMAIL and PAYPAL_PASSWORD):
            self.fail('No PayPal credentials supplied!')

        self._start_checkout()
        self.checkout_with_paypal()

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')
