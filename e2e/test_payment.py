import datetime
import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

from e2e.api import DiscoveryApi, EcommerceApi, EnrollmentApi
from e2e.config import LMS_USERNAME, PAYPAL_EMAIL, PAYPAL_PASSWORD
from e2e.constants import ADDRESS_FR, ADDRESS_US
from e2e.helpers import EcommerceHelpers, LmsHelpers

log = logging.getLogger(__name__)


class TestSeatPayment(object):
    def get_verified_course_run(self):
        """ Returns a course run data dict. """
        return DiscoveryApi().get_course_run('verified')

    def checkout_with_credit_card(self, selenium, address):
        """ Submits the credit card form hosted by the E-Commerce Service. """
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
            ('id_country', country),
            ('card-expiry-month', '12'),
            ('card-expiry-year', card_expiry_year),
        ]

        if country in ('US', 'CA',):
            select_fields.append(('id_state', state,))
        else:
            billing_information['id_state'] = state

        # Select the appropriate <option> elements
        for selector, value in select_fields:
            if value:
                select = Select(selenium.find_element_by_id(selector))
                select.select_by_value(value)

        # Fill in the text fields
        for field, value in billing_information.items():
            selenium.find_element_by_id(field).send_keys(value)

        # Click the payment button
        selenium.find_element_by_id('payment-button').click()

    def checkout_with_paypal(self, selenium):
        selenium.find_element_by_css_selector('button.payment-button[data-processor-name=paypal]').click()

        # Wait for login form to load. PayPal's test environment is slow.
        login_iframe = selenium.find_element_by_css_selector('#injectedUnifiedLogin > iframe')
        selenium.switch_to.frame(login_iframe)

        # Log into PayPal
        email = selenium.find_element_by_id('email')
        password = selenium.find_element_by_id('password')
        email.send_keys(PAYPAL_EMAIL)
        password.send_keys(PAYPAL_PASSWORD)

        selenium.find_element_by_id('btnLogin').click()
        selenium.switch_to.default_content()

        # Wait for the checkout form to load, and for the loading spinner to disappear.
        wait = WebDriverWait(selenium, 10)
        spinner_invisibility = EC.invisibility_of_element_located((By.ID, 'spinner'))
        wait.until(spinner_invisibility)
        selenium.find_element_by_id('confirmButtonTop').click()

    def assert_browser_on_receipt_page(self, selenium):
        selenium.find_element_by_id('receipt-container')

    def assert_user_enrolled_in_course_run(self, username, course_run_key, seat_type='verified', attempts=5):
        """ Asserts the given user has an *active* enrollment for the given course run and seat type/mode.

         Args:
             username (str): Username of the user whose enrollments should be retrieved.
             course_run_key (str): ID of the course run for which enrollments should be retrieved.
             seat_type (str): Expected enrolled seat type/mode
             attempts (int): Number of times to attempt to retrieve the enrollment data.

         Raises:
             AssertionError if no active enrollment is found that matches the criteria.
        """
        api = EnrollmentApi()

        while attempts > 0:
            attempts -= 1
            log.info('Retrieving enrollment details for [%s] in [%s]...', username, course_run_key)
            enrollment = api.get_enrollment(username, course_run_key)

            try:
                assert enrollment['is_active'] and enrollment['mode'] == seat_type
                return
            except AssertionError:
                log.warning('No active enrollment was found for [%s] in the [%s] mode of [%s].',
                            username, seat_type, course_run_key)
                if attempts < 1:
                    raise

                log.info('Checking again in 0.5 seconds.')
                time.sleep(0.5)

    def add_item_to_basket(self, selenium, sku):
        # Add the item to the basket and start the checkout process
        selenium.get(EcommerceHelpers.build_url('/basket/add/?sku=' + sku))
        assert selenium.find_element_by_css_selector('.basket-client-side').is_displayed()

    def refund_orders_for_course_run(self, course_run_id):
        api = EcommerceApi()
        refund_ids = api.create_refunds_for_course_run(LMS_USERNAME, course_run_id)
        assert len(refund_ids) > 0

        for refund_id in refund_ids:
            api.process_refund(refund_id, 'approve')

    def get_verified_seat(self, course_run):
        verified_seat = None
        for seat in course_run['seats']:
            if seat['type'] == 'verified':
                verified_seat = seat
                break
        return verified_seat

    def test_verified_seat_payment_with_credit_card(self, selenium):
        """ Validates users can add a verified seat to the cart and checkout with a credit card. """
        LmsHelpers.login(selenium)

        # Get the course run we want to purchase
        course_run = self.get_verified_course_run()
        verified_seat = self.get_verified_seat(course_run)

        for address in (ADDRESS_US, ADDRESS_FR,):
            self.add_item_to_basket(selenium, verified_seat['sku'])
            self.checkout_with_credit_card(selenium, address)
            self.assert_browser_on_receipt_page(selenium)

            course_run_key = course_run['key']
            self.assert_user_enrolled_in_course_run(LMS_USERNAME, course_run_key)
            self.refund_orders_for_course_run(course_run_key)

    def test_verified_seat_payment_with_paypal(self, selenium):
        """ Validates users can add a verified seat to the cart and checkout with PayPal. """
        LmsHelpers.login(selenium)

        # Get the course run we want to purchase
        course_run = self.get_verified_course_run()
        verified_seat = self.get_verified_seat(course_run)
        self.add_item_to_basket(selenium, verified_seat['sku'])
        self.checkout_with_paypal(selenium)
        self.assert_browser_on_receipt_page(selenium)

        course_run_key = course_run['key']
        self.assert_user_enrolled_in_course_run(LMS_USERNAME, course_run_key)
        self.refund_orders_for_course_run(course_run_key)
