import datetime
import logging
import time
import uuid

import requests
from edx_rest_api_client.client import EdxRestApiClient
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from e2e.api import EnrollmentApiClient, get_access_token
from e2e.config import (
    BASIC_AUTH_PASSWORD, BASIC_AUTH_USERNAME, ECOMMERCE_API_URL, ECOMMERCE_URL_ROOT, LMS_AUTO_AUTH, LMS_EMAIL,
    LMS_HTTPS, LMS_PASSWORD, LMS_URL_ROOT, LMS_USERNAME, MARKETING_URL_ROOT, MAX_COMPLETION_RETRIES, PAYPAL_EMAIL,
    PAYPAL_PASSWORD
)
from e2e.expected_conditions import input_provided
from e2e.pages import submit_lms_login_form
from e2e.pages.ecommerce import EcommerceLoginPage
from e2e.pages.lms import LMSDashboardPage, LMSLoginPage, LMSLogoutPage, LMSRegistrationPage

log = logging.getLogger(__name__)


class LmsUserMixin(object):
    password = 'edx'

    def get_lms_user(self):
        if LMS_AUTO_AUTH:
            return self.create_lms_user()

        return LMS_USERNAME, LMS_PASSWORD, LMS_EMAIL

    def generate_user_credentials(self, username_prefix):
        username = username_prefix + uuid.uuid4().hex[0:10]
        password = self.password
        email = '{}@example.com'.format(username)
        return username, email, password

    def create_lms_user(self):
        username, email, password = self.generate_user_credentials(username_prefix='auto_auth_')

        url = '{host}/auto_auth?no_login=true&username={username}&password={password}&email={email}'.format(
            host=LMS_URL_ROOT,
            username=username,
            password=password,
            email=email
        )
        auth = None

        if BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD:
            auth = (BASIC_AUTH_USERNAME, BASIC_AUTH_PASSWORD)

        requests.get(url, auth=auth)

        return username, password, email


class LogistrationMixin(LmsUserMixin):
    def setUp(self):
        super(LogistrationMixin, self).setUp()
        self.lms_login_page = LMSLoginPage(self.browser)
        self.lms_registration_page = LMSRegistrationPage(self.browser)

    def login_with_lms(self, email=None, password=None, course_id=None):
        """ Visit LMS and login. """
        email = email or LMS_EMAIL
        password = password or LMS_PASSWORD

        self.lms_login_page.visit(course_id)
        self.lms_login_page.login(email, password)

    def register_via_ui(self, course_id=None):
        """ Creates a new account via the normal user interface. """
        username, email, password = self.generate_user_credentials(username_prefix='otto_acceptance_')
        url = self.lms_registration_page.url(course_id)  # pylint: disable=not-callable
        self.lms_registration_page.browser.get(url)
        self.lms_registration_page.register_and_login(username, username, email, password)

        return username, email, password


class LMSLogoutMixin(object):
    def setUp(self):
        super(LMSLogoutMixin, self).setUp()
        self.lms_logout_page = LMSLogoutPage(self.browser)

    def assert_on_lms_logout_page(self):
        lms_homepage_url = MARKETING_URL_ROOT or LMS_URL_ROOT
        self.assertTrue(self.browser.current_url.startswith(lms_homepage_url))

    def logout_via_lms(self):
        self.lms_logout_page.visit()


def login_with_lms(self, email=None, password=None, course_id=None):
    """ Visit LMS and login. """
    email = email or LMS_EMAIL
    password = password or LMS_PASSWORD

    self.lms_login_page.visit(course_id)
    self.lms_login_page.login(email, password)


class OttoAuthenticationMixin(object):
    def setUp(self):
        super(OttoAuthenticationMixin, self).setUp()
        self.otto_login_page = EcommerceLoginPage(self.browser)

    def login_via_otto(self, email=None, password=None):
        """ Start the login process via Otto's login page (which should redirect to LMS.) """
        email = email or LMS_EMAIL
        password = password or LMS_PASSWORD

        # Note: We have to visit LMS Login page to provide basic auth as otto login page redirect to LMS login page
        # which requires basic auth and not providing that could cause the test to hang.
        lms_login_page = LMSLoginPage(self.browser)
        lms_login_page.visit()

        self.otto_login_page.visit()
        submit_lms_login_form(self.otto_login_page, email, password)

    def logout_via_otto(self):
        url = '{}/logout/'.format(ECOMMERCE_URL_ROOT)
        self.browser.get(url)


class EnrollmentApiMixin(object):
    def setUp(self):
        super(EnrollmentApiMixin, self).setUp()
        self.enrollment_api_client = EnrollmentApiClient()

    def assert_user_enrolled(self, username, course_id, mode='honor'):
        """ Verify the user is enrolled in the given course and mode. """
        status = self.enrollment_api_client.get_enrollment_status(username, course_id)
        self.assertDictContainsSubset({'is_active': True, 'mode': mode}, status)

    def assert_user_not_enrolled(self, username, course_id):
        """ Verify the user is NOT enrolled in the given course. """
        try:
            status = self.enrollment_api_client.get_enrollment_status(username, course_id)
        except ValueError:
            # Silly Enrollment API doesn't actually return data if an enrollment does not exist.
            return

        # If/when the API is updated, use this code to check enrollment status.
        if status:
            msg = '{} should NOT be enrolled in {}'.format(username, course_id)
            self.assertDictContainsSubset({'is_active': False}, status, msg)


class EcommerceApiMixin(object):
    @property
    def ecommerce_api_client(self):
        access_token, __ = get_access_token()
        return EdxRestApiClient(ECOMMERCE_API_URL, jwt=access_token)

    def assert_order_created_and_completed(self):
        orders = self.ecommerce_api_client.orders.get()['results']
        self.assertGreater(len(orders), 0, 'No orders found for the user!')

        # TODO Validate this is the correct order.
        order = orders[0]
        self.assertTrue(self._verify_completion(order))

    def _verify_completion(self, order):
        """Check a configurable number of times to see if the order is complete."""
        is_complete = True if order['status'] == 'Complete' else False
        retries = 0
        number = order['number']

        while not is_complete and retries < MAX_COMPLETION_RETRIES:
            order = self.ecommerce_api_client.orders(number).get()
            if order['status'] == 'Complete':
                is_complete = True
            else:
                retries += 1

        return is_complete


class UnenrollmentMixin(object):
    def tearDown(self):
        self.unenroll_via_dashboard(self.course_id)
        super(UnenrollmentMixin, self).tearDown()

    def unenroll_via_dashboard(self, course_id):
        """ Unenroll the current user from a course via the LMS dashboard. """
        LMSDashboardPage(self.browser).visit()

        # Find the (hidden) unenroll link
        unenroll_link = self.browser.find_element_by_css_selector(
            'a.action-unenroll[data-course-id="{}"]'.format(course_id))

        # Show the link by clicking on the parent element
        unenroll_link.find_element_by_xpath(".//ancestor::div[contains(@class, 'wrapper-action-more')]/button").click()

        # Unenroll
        unenroll_link.click()
        self.browser.find_element_by_css_selector('#unenroll_form input[name=submit]').click()


class PaymentMixin(object):
    def dismiss_alert(self):
        """
        If we are testing locally with a non-HTTPS LMS instance, a security alert may appear when transitioning to
        secure pages. This method dismisses them.
        """
        if not LMS_HTTPS:
            try:
                WebDriverWait(self.browser, 2).until(EC.alert_is_present())
                self.browser.switch_to_alert().accept()
            except TimeoutException:
                pass

    def wait_for_payment_form(self):
        """ Wait for the payment form to load. """
        wait = WebDriverWait(self.browser, 10)
        wait.until(EC.presence_of_element_located((By.ID, 'paymentForm')))

    def checkout_with_paypal(self):
        """ Completes the checkout process via PayPal. """
        self.wait_for_payment_form()

        # Wait for the button handler to be setup
        time.sleep(0.5)

        # Click the payment button
        self.browser.find_element_by_css_selector('button.payment-button[data-processor-name=paypal]').click()

        # Wait for login form to load. PayPal's test environment is slow.
        wait = WebDriverWait(self.browser, 30)
        login_iframe = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#injectedUnifiedLogin > iframe')))
        # TODO Determine how to get past the TypeError here.
        self.browser.switch_to.frame(login_iframe)

        # Log into PayPal
        email = self.browser.find_element_by_css_selector('input#email')
        password = self.browser.find_element_by_css_selector('input#password')

        # Sometimes, keys aren't sent to the inputs on the first attempt.
        for _ in range(3):
            if not email.get_attribute('value'):
                email.send_keys(PAYPAL_EMAIL)

            if not password.get_attribute('value'):
                password.send_keys(PAYPAL_PASSWORD)

        # If credentials can't be entered, prevent the test from advancing.
        # This makes debugging easier.
        wait = WebDriverWait(self.browser, 2)
        credentials_provided = input_provided(email, password)
        wait.until(credentials_provided)

        self.browser.find_element_by_css_selector('button[type="submit"]').click()
        self.browser.switch_to.default_content()

        # Wait for the checkout form to load. PayPal's test environment is slow.
        wait = WebDriverWait(self.browser, 30)
        confirmation_button_present = EC.presence_of_element_located((By.ID, 'confirmButtonTop'))
        confirmation_button = wait.until(confirmation_button_present)

        # PayPal's loading spinner sticks around for longer than it should.
        wait = WebDriverWait(self.browser, 2)
        spinner_invisibility = EC.invisibility_of_element_located((By.ID, 'spinner'))
        wait.until(spinner_invisibility)

        confirmation_button.click()

    def checkout_with_credit_card(self, address):
        """ Submit the payment form. """
        self.wait_for_payment_form()

        billing_information = {
            'id_first_name': 'Ed',
            'id_last_name': 'Xavier',
            'id_address_line1': address['line1'],
            'id_address_line2': address['line2'],
            'id_city': address['city'],
            'id_postal_code': address['postal_code'],
            'card-number': '4111111111111111',
            'card-cvn': '123'
        }

        country = address['country']
        state = address['state'] or ''

        card_expiry_year = str(datetime.datetime.now().year + 3)
        select_fields = [
            ('#id_country', country),
            ('#card-expiry-month', '12'),
            ('#card-expiry-year', card_expiry_year),
        ]

        if country in ('US', 'CA',):
            select_fields.append(('#id_state', state,))
        else:
            billing_information['id_state'] = state

        # Select the appropriate <option> elements
        for selector, value in select_fields:
            if value:
                select = Select(self.browser.find_element_by_css_selector(selector))
                select.select_by_value(value)

        # Fill in the text fields
        for field, value in billing_information.items():
            self.browser.find_element_by_css_selector('#' + field).send_keys(value)

        # Click the payment button
        self.browser.find_element_by_css_selector('#payment-button').click()

    def assert_receipt_page_loads(self):
        """ Verifies the receipt page loaded in the browser. """
        refresh = False

        # In a test environment, it can take a while for the payment processor to respond.
        for _ in range(MAX_COMPLETION_RETRIES):
            try:
                if refresh:
                    self.browser.refresh()
                    WebDriverWait(self.browser, 2).until(EC.alert_is_present())
                    self.browser.switch_to.alert.accept()

                # Wait for the payment processor response to be processed, and the receipt page updated.
                wait = WebDriverWait(self.browser, 10)
                receipt_loaded = EC.presence_of_element_located((By.CLASS_NAME, 'content-main'))
                wait.until(receipt_loaded)

                break
            except TimeoutException:
                refresh = True

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

        # Confirm the thank you message is not broken (ref: WL-466 + edx/edx-platform#12476)
        css_selector = 'span.course_name_placeholder'
        course_name_placeholder_text = self.browser.find_elements_by_css_selector(css_selector)[0].text
        title = line['product']['title']
        self.assertIn(course_name_placeholder_text, title)


class CouponMixin(EcommerceApiMixin):
    discount_coupon_name = 'test-discount-code-'
    enrollment_coupon_name = 'test-enrollment-code-'

    def tearDown(self):
        """Remove coupons and vouchers"""
        self.get_and_delete_coupons(self.discount_coupon_name)
        self.get_and_delete_coupons(self.enrollment_coupon_name)
        super(CouponMixin, self).tearDown()

    def get_and_delete_coupons(self, partial_title):
        """
        Get all coupons created in the e2e tests and delete those
        and all associated stock records and vouchers.
        """
        coupons = self.ecommerce_api_client.coupons.get(title=partial_title)['results']
        for coupon in coupons:
            self.ecommerce_api_client.coupons(coupon['id']).delete()
