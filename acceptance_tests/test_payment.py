from bok_choy.web_app_test import WebAppTest
import ddt
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from acceptance_tests.config import VERIFIED_COURSE_ID, HTTPS_RECEIPT_PAGE, PAYPAL_PASSWORD, PAYPAL_EMAIL
from acceptance_tests.mixins import LogistrationMixin, EnrollmentApiMixin, EcommerceApiMixin, UnenrollmentMixin
from acceptance_tests.pages import LMSCourseModePage


@ddt.ddt
class VerifiedCertificatePaymentTests(UnenrollmentMixin, EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin,
                                      WebAppTest):
    def setUp(self):
        super(VerifiedCertificatePaymentTests, self).setUp()
        self.course_id = VERIFIED_COURSE_ID
        self.username, self.password, self.email = self.get_lms_user()

    def _start_checkout(self):
        """ Begin the checkout process for a verified certificate. """
        self.login_with_lms(self.email, self.password)
        course_modes_page = LMSCourseModePage(self.browser, self.course_id)
        course_modes_page.visit()

        # Click the purchase button on the track selection page to take
        # the browser to the payment selection page.
        course_modes_page.q(css='input[name=verified_mode]').click()

    def assert_receipt_page_loads(self):
        """ Verifies the receipt page loaded in the browser. """

        # Wait for the payment processor response to be processed, and the receipt page updated.
        WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'content-main')))

        # Verify we reach the receipt page.
        self.assertIn('receipt', self.browser.title.lower())

        # Check the content of the page
        cells = self.browser.find_elements_by_css_selector('table.report-receipt tbody td')
        self.assertGreater(len(cells), 0)
        order = self.ecommerce_api_client.orders.get()['results'][0]
        line = order['lines'][0]
        expected = [
            order['number'],
            line['description'],
            order['date_placed'],
            '{amount} ({currency})'.format(amount=line['line_price_excl_tax'], currency=order['currency'])
        ]
        actual = [cell.text for cell in cells]
        self.assertListEqual(actual, expected)

    def _dismiss_alert(self):
        """
        If we are testing locally with a non-HTTPS LMS instance, a security alert may appear when transitioning to
        secure pages. This method dismisses them.
        """
        if not HTTPS_RECEIPT_PAGE:
            try:
                WebDriverWait(self.browser, 2).until(EC.alert_is_present())
                self.browser.switch_to_alert().accept()
            except TimeoutException:
                pass

    def _checkout_with_cybersource(self, address):
        """ Completes the checkout process via CyberSource. """

        # Click the payment button
        self.browser.find_element_by_css_selector('#cybersource').click()

        self._dismiss_alert()

        # Wait for form to load
        WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.ID, 'billing_details')))

        # Select the credit card type (Visa) first since it triggers the display of additional fields
        self.browser.find_element_by_css_selector('#card_type_001').click()  # Visa

        # Select the appropriate <option> elements
        select_fields = (
            ('#bill_to_address_country', address['country']),
            ('#bill_to_address_state_us_ca', address['state']),
            ('#card_expiry_year', '2020')
        )
        for selector, value in select_fields:
            if value:
                select = Select(self.browser.find_element_by_css_selector(selector))
                select.select_by_value(value)

        # Fill in the text fields
        billing_information = {
            'bill_to_forename': 'Ed',
            'bill_to_surname': 'Xavier',
            'bill_to_address_line1': address['line1'],
            'bill_to_address_line2': address['line2'],
            'bill_to_address_city': address['city'],
            'bill_to_address_postal_code': address['postal_code'],
            'bill_to_email': 'edx@example.com',
            'card_number': '4111111111111111',
            'card_cvn': '1234'
        }

        for field, value in billing_information.items():
            self.browser.find_element_by_css_selector('#' + field).send_keys(value)

        # Click the payment button
        self.browser.find_element_by_css_selector('input[type=submit]').click()

        self._dismiss_alert()

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
    def test_cybersource(self, address):
        """ Test checkout with CyberSource. """
        self._start_checkout()
        self._checkout_with_cybersource(address)

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')

    def _checkout_with_paypal(self):
        """ Completes the checkout process via PayPal. """

        # Click the payment button
        self.browser.find_element_by_css_selector('#paypal').click()

        # Make sure we are checking out with a PayPal account, instead of credit card
        try:
            WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.ID, 'loadLogin')))
            self.browser.find_element_by_css_selector('#loadLogin').click()
        except (NoSuchElementException, TimeoutException):
            # The PayPal form may be visible by default.
            pass

        # Wait for form to load
        WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.ID, 'login_email')))

        # Log into PayPal
        self.browser.find_element_by_css_selector('input#login_email').send_keys(PAYPAL_EMAIL)
        self.browser.find_element_by_css_selector('input#login_password').send_keys(PAYPAL_PASSWORD)
        self.browser.find_element_by_css_selector('input#submitLogin').click()

        # Checkout
        self.browser.find_element_by_css_selector('input#continue').click()

    def test_paypal(self):
        """ Test checkout with PayPal. """

        if not (PAYPAL_EMAIL and PAYPAL_PASSWORD):
            self.fail('No PayPal credentials supplied!')

        self._start_checkout()
        self._checkout_with_paypal()

        self.assert_receipt_page_loads()
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id, 'verified')
