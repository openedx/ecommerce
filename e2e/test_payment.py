import datetime
import logging
import time


from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.keys import Keys


from e2e.api import EcommerceApi, EnrollmentApi
from e2e.config import LMS_USERNAME
from e2e.constants import ADDRESS_FR, ADDRESS_US
from e2e.helpers import EcommerceHelpers, LmsHelpers
from e2e.constants import TEST_COURSE_KEY

log = logging.getLogger(__name__)


class TestSeatPayment(object):
    def checkout_with_credit_card(self, selenium, address):
        """ Submits the credit card form hosted by the E-Commerce Service. """
        billing_information = {
            'id_first_name': 'Ed',
            'id_last_name': 'Xavier',
            'id_address_line1': address['line1'],
            'id_address_line2': address['line2'],
            'id_city': address['city'],
            'id_postal_code': address['postal_code'],
        }

        country = address['country']
        state = address['state'] or ''

        card_expiry_year = str(datetime.datetime.now().year + 3)
        select_fields = [
            ('id_country', country)
        ]

        if country in ('US', 'CA',):
            select_fields.append(('id_state', state,))
        else:
            billing_information['id_state'] = state

        try:
            selenium.find_element_by_css_selector('div#iframe')

            selenium.switch_to.frame("payment_iframe")

            selenium.find_element_by_id('id_number_input').send_keys('4111111111111111')
            selenium.find_element_by_id('id_expy_input').send_keys('0422')
            selenium.find_element_by_id('id_cvv_input').send_keys('123')

            selenium.switch_to.default_content()

        except NoSuchElementException:
            select_fields = select_fields + [
                ('card-expiry-month', '12'),
                ('card-expiry-year', card_expiry_year)
            ]

            billing_information.update({
                'card-number': '4111111111111111',
                'card-cvn': '123'
            })

        # Select the appropriate <option> elements
        for selector, value in select_fields:
            if value:
                select = Select(selenium.find_element_by_id(selector))
                select.select_by_value(value)

        # Fill in the text fields
        for field, value in billing_information.items():
            selenium.find_element_by_id(field).send_keys(value)

        # Click the payment button
        selenium.find_element_by_id('payment-button').send_keys("\n")

    def assert_browser_on_receipt_page(self, selenium):
        WebDriverWait(selenium, 20).until(
            EC.visibility_of_element_located((By.ID, 'receipt-container'))
        )

    def assert_course_is_verified(self, selenium):
        EcommerceHelpers.visit_course_page(selenium)
        assert selenium.find_element_by_css_selector('div.course-id').text == TEST_COURSE_KEY

    def assert_user_enrolled_in_course_run(self, username, seat_type='verified', attempts=5):
        """ Asserts the given user has an *active* enrollment for the given course run and seat type/mode.

         Args:
             username (str): Username of the user whose enrollments should be retrieved.
             seat_type (str): Expected enrolled seat type/mode
             attempts (int): Number of times to attempt to retrieve the enrollment data.

         Raises:
             AssertionError if no active enrollment is found that matches the criteria.
        """
        api = EnrollmentApi()

        while attempts > 0:
            attempts -= 1
            log.info('Retrieving enrollment details for [%s] in [%s]...', username, TEST_COURSE_KEY)
            enrollment = api.get_enrollment(username, TEST_COURSE_KEY)

            try:
                assert enrollment['is_active'] and enrollment['mode'] == seat_type
                return
            except AssertionError:
                log.warning('No active enrollment was found for [%s] in the [%s] mode of [%s].',
                            username, seat_type, TEST_COURSE_KEY)
                if attempts < 1:
                    raise

                log.info('Checking again in 0.5 seconds.')
                time.sleep(0.5)

    def add_item_to_basket(self, selenium):
        # Add the item to the basket and start the checkout process
        selenium.get(LmsHelpers.build_url('dashboard'))
        course_title = 'course-title-' + TEST_COURSE_KEY
        button_css_selector =  "article[aria-labelledby='{}'] footer a.action-upgrade".format(course_title)
        selenium.find_element_by_css_selector(button_css_selector).send_keys("\n")

        # Wait till the selector is visible
        WebDriverWait(selenium, 20).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, ".basket-client-side"))
        )

    def refund_orders_for_course_run(self):
        api = EcommerceApi()
        refund_ids = api.create_refunds_for_course_run(LMS_USERNAME, TEST_COURSE_KEY)
        assert len(refund_ids) > 0

        for refund_id in refund_ids:
            api.process_refund(refund_id, 'approve')
        return True


    def test_verified_seat_payment_with_credit_card(self, selenium):
        """
        Validates users can add a verified seat to the cart and checkout with a credit card.
        This test requires 'disable_repeat_order_check' waffle switch turned off on stage, to run.
        """

        LmsHelpers.login(selenium)

        #enroll user if not already enrolled in given course
        try:
            self.assert_user_enrolled_in_course_run(LMS_USERNAME, 'audit')
        except AssertionError:
            LmsHelpers.enroll_user(selenium)

        #add course to ecommerce if not verified
        try:
            self.assert_course_is_verified(selenium)
        except NoSuchElementException:
            EcommerceHelpers.add_course_to_ecommerce(selenium)

        for address in (ADDRESS_US, ADDRESS_FR,):
            time.sleep(0.5)
            self.add_item_to_basket(selenium)
            self.checkout_with_credit_card(selenium, address)
            self.assert_browser_on_receipt_page(selenium)
            self.assert_user_enrolled_in_course_run(LMS_USERNAME)
            assert self.refund_orders_for_course_run()
            LmsHelpers.enroll_user(selenium)
