from unittest import skipUnless

from bok_choy.web_app_test import WebAppTest
import ddt
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from acceptance_tests.config import (VERIFIED_COURSE_ID, MARKETING_URL_ROOT,
                                     ENABLE_PAYPAL_TESTS, ENABLE_STRIPE_TESTS
                                     PAYPAL_PASSWORD, PAYPAL_EMAIL, ENABLE_CYBERSOURCE_TESTS)
from acceptance_tests.constants import CYBERSOURCE_DATA1, CYBERSOURCE_DATA2
from acceptance_tests.mixins import (LogistrationMixin, EnrollmentApiMixin, EcommerceApiMixin,
                                     PaymentMixin, UnenrollmentMixin)
from acceptance_tests.pages import LMSCourseModePage, MarketingCourseAboutPage


class VerifiedCertificateMixin(object):

    def setUp(self):
        super(VerifiedCertificateMixin, self).setUp()
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


@ddt.ddt
class VerifiedCertificatePaymentTests(
        UnenrollmentMixin, EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin,
        VerifiedCertificateMixin, PaymentMixin, WebAppTest):

    @skipUnless(ENABLE_CYBERSOURCE_TESTS, 'CyberSource tests are not enabled.')
    @ddt.data(CYBERSOURCE_DATA1, CYBERSOURCE_DATA2)
    def test_cybersource(self, address):
        """ Test checkout with CyberSource. """
        self._start_checkout()
        self.checkout_with_cybersource(address)

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')

    @skipUnless(ENABLE_PAYPAL_TESTS, 'PayPal tests are not enabled.')
    def test_paypal(self):
        """ Test checkout with PayPal. """
        if not (PAYPAL_EMAIL and PAYPAL_PASSWORD):
            self.fail('No PayPal credentials supplied!')

        self._start_checkout()
        self.checkout_with_paypal()

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')


@ddt.ddt
@skipUnless(ENABLE_STRIPE_TESTS, 'Stripe tests are not enabled.')
class TestStripePayment(
        UnenrollmentMixin, EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin,
        VerifiedCertificateMixin, PaymentMixin, WebAppTest):

    def unenroll_via_dashboard(self, *args, **kwargs):
        # This is a clean-up action that raises an exception if a student
        # is not enrolled. Fot this test this behaviour is not desired as some of
        # the methods will result in student being enrolled, and some
        # (for example: failed payments) don't.
        # However at the end of every test students need to be
        # un-enrolled.
        try:
            super(TestStripePayment, self).unenroll_via_dashboard(*args, **kwargs)
        except NoSuchElementException:
            pass

    def assert_user_not_verified(self, username, course_id):
        status = self.enrollment_api_client.get_enrollment_status(username, course_id)
        self.assertTrue(
            not status['is_active'] or status['mode'] != 'verified'
        )

    @ddt.data(
        # These are valid cards of different kinds
        # (different issuers, debit vs credit)
        # Format is: (card no, expiry MMYY, CCV code)
        ("4242424242424242", "1234", "1234"),
        ("30569309025904", "1234", "1234"),
        ("5105105105105100", "1234", "1234"),
    )
    def test_stripe_payment(self, cc_data):
        self._start_checkout()
        self.checkout_with_stripe(*cc_data)
        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')

    @ddt.data(
        # Format is: (card no, expiry MMYY, CCV code)
        # This is a special "Invalid" card no
        ('4000000000000002', "1234", "1234"),
        # This card will fail on any CVC
        ('4000000000000127', "1234", "1234"),
        # This card has a valid number, but no funds
        ('4000000000000119', "1234", "1234"),
    )
    def test_stripe_payment_failed_on_checkout(self, cc_data):
        # This test checks for various cases where payment fails
        # but failure is handled by checkout.js from stripe
        # (and user primarily interacts with the stripe checkout code).

        # Sanity check:
        self.assert_user_not_verified(self.username, self.course_id)
        self._start_checkout()
        self.browser.find_element_by_css_selector('#stripe').click()
        submitter = self.fill_stripe_cc_details(*cc_data)
        submitter(switch_back=False)
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR, 'form.shake.checkoutView')))

        self.assert_user_not_verified(self.username, self.course_id)

    @ddt.data(
        # These two are special cards that fail only when we
        # attempt to make an actual charge (and not on checkout.js
        # code)
        ("4000000000000341", "1234", "1234"),
        ("4100000000000019", "1234", "1234"),
    )
    def test_stripe_payment_that_fails_during_processing(self, cc_data):
        # This test checks for various cases where card passes through
        # checkout.js and fails during charging the card on our server.
        # In this test user is redirected to the payment error page on LMS

        # Sanity check
        self.assert_user_not_verified(self.username, self.course_id)
        self._start_checkout()
        self.checkout_with_stripe(*cc_data)
        WebDriverWait(self.browser, 10).until(
            EC.title_contains("Checkout Error")
        )
        self.assert_user_not_verified(self.username, self.course_id)
