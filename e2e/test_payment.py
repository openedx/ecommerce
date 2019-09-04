from __future__ import absolute_import

import datetime
import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

from e2e.api import DiscoveryApi, EcommerceApi, EnrollmentApi
from e2e.config import LMS_USERNAME
from e2e.constants import ADDRESS_FR, ADDRESS_US
from e2e.helpers import EcommerceHelpers, LmsHelpers

log = logging.getLogger(__name__)


class TestSeatPayment(object):
    def get_verified_course_run(self):
        """ Returns a course run data dict. """
        return DiscoveryApi().get_course_run('verified')

    def checkout_with_credit_card(self, selenium, address, is_new_payment_page):
        """
        Submits the credit card form hosted by the E-Commerce Service.

        Arguments:
            is_new_payment_page (bool): True to test the new payment page, False to test the older basket page.
        """
        if is_new_payment_page:
            billing_information = {
                'firstName': 'Ed',
                'lastName': 'Xavier',
                'address': address['line1'],
                'unit': address['line2'],
                'city': address['city'],
                'postalCode': address['postal_code'],
                'cardNumber': '4111111111111111',
                'securityCode': '123'
            }
        else:
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
        if is_new_payment_page:
            select_fields = [
                (By.ID, 'country', country),
                (By.ID, 'cardExpirationMonth', '12'),
                (By.ID, 'cardExpirationYear', card_expiry_year),
            ]

            if country in ('US', 'CA',):
                # Ensure the state field has time to switch from text to select field for certain countries
                # Note: This is still flaky.  Also tried xpath './/select[@id='state']'.
                select_fields.append((By.XPATH, ".//label[@for='state']/following-sibling::select", state))
            else:
                billing_information['state'] = state
        else:
            select_fields = [
                (By.ID, 'id_country', country),
                (By.ID, 'card-expiry-month', '12'),
                (By.ID, 'card-expiry-year', card_expiry_year),
            ]

            if country in ('US', 'CA',):
                select_fields.append((By.ID, 'id_state', state))
            else:
                billing_information['id_state'] = state

        # Select the appropriate <option> elements
        for locator_type, selector, value in select_fields:
            if value:
                try:
                    element = WebDriverWait(selenium, 30).until(
                        EC.presence_of_element_located((locator_type, selector))
                    )
                except:
                    raise Exception('Timeout exception with locator (%s, %s).' % (locator_type, selector))

                select = Select(element)
                select.select_by_value(value)

        # Fill in the text fields
        for field, value in billing_information.items():
            selenium.find_element_by_id(field).send_keys(value)

        # Click the payment button
        if is_new_payment_page:
            selenium.find_element_by_id('placeOrderButton').click()
        else:
            selenium.find_element_by_id('payment-button').click()

    def assert_browser_on_receipt_page(self, selenium):
        # Long delay is possible due to SSO which starts with the receipt page.
        WebDriverWait(selenium, 45).until(
            EC.visibility_of_element_located((By.ID, 'receipt-container'))
        )

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

    def add_item_to_basket(self, selenium, sku, is_new_payment_page):
        """
        Arguments:
            is_new_payment_page (bool): True to test the new payment page, False to test the older basket page.
        """
        if is_new_payment_page:
            microfrontend_waffle_flag_enabled = 1
            page_css_selector = ".page__payment"
        else:
            microfrontend_waffle_flag_enabled = 0
            page_css_selector = ".basket-client-side"

        # Note: although not intuitive, the waffle flag `force_microfrontend_bucket` must be enabled to allow the
        #   waffle flag `enable_microfrontend_for_basket_page` to function.
        force_microfrontend_bucket_flag_enabled = 1

        # Add the item to the basket and start the checkout process
        selenium.get(EcommerceHelpers.build_url(
            '/basket/add/?sku={}'
            '&dwft_enable_microfrontend_for_basket_page={}'
            '&dwft_force_microfrontend_bucket={}'.format(
                sku,
                microfrontend_waffle_flag_enabled,
                force_microfrontend_bucket_flag_enabled,
            )
        ))

        # Wait till the selector is visible
        WebDriverWait(selenium, 20).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, page_css_selector))
        )

    def refund_orders_for_course_run(self, course_run_id):
        api = EcommerceApi()
        refund_ids = api.create_refunds_for_course_run(LMS_USERNAME, course_run_id)
        assert refund_ids != []

        for refund_id in refund_ids:
            api.process_refund(refund_id, 'approve')
        return True

    def get_verified_seat(self, course_run):
        verified_seat = None
        for seat in course_run['seats']:
            if seat['type'] == 'verified':
                verified_seat = seat
                break
        return verified_seat

    def verified_seat_payment_with_credit_card(self, selenium, is_new_payment_page, addresses):
        """
        Validates users can add a verified seat to the cart and checkout with a credit card.

        Arguments:
            is_new_payment_page (bool): True to test the new payment page, False to test the older basket page.
            addresses (tuple): Addresses to test.

        This test requires 'disable_repeat_order_check' waffle switch turned off on stage, to run.

        """
        LmsHelpers.login(selenium)

        # Get the course run we want to purchase
        course_run = self.get_verified_course_run()
        verified_seat = self.get_verified_seat(course_run)

        try:

            for address in addresses:
                self.add_item_to_basket(selenium, verified_seat['sku'], is_new_payment_page)
                self.checkout_with_credit_card(selenium, address, is_new_payment_page)
                self.assert_browser_on_receipt_page(selenium)

                course_run_key = course_run['key']
                self.assert_user_enrolled_in_course_run(LMS_USERNAME, course_run_key)
                assert self.refund_orders_for_course_run(course_run_key)

        except Exception as exception:
            current_url = None
            page_source = None
            try:
                current_url = selenium.current_url
            except:
                pass
            try:
                # Use innerHTML to get dynamically injected HTML as well as server-side HTML.
                page_source = selenium.execute_script(
                    "return document.documentElement.innerHTML.toLowerCase()"
                )
            except:
                pass
            exception_message = u'{}\n\nFailing URL: {}\n\nFailing HTML: {}'.format(
                exception.message,
                current_url,
                page_source,
            )
            raise Exception(exception_message)

    def test_verified_seat_payment_with_credit_card_basket_page(self, selenium):
        """
        Using the basket page, validates users can add a verified seat to the cart and
        checkout with a credit card.

        This test requires 'disable_repeat_order_check' waffle switch turned off on stage, to run.
        """
        self.verified_seat_payment_with_credit_card(
            selenium,
            is_new_payment_page=False,
            addresses=(ADDRESS_US, ADDRESS_FR,)
        )

    def test_verified_seat_payment_with_credit_card_payment_page(self, selenium):
        """
        Using the payment microfrontend page, validates users can add a verified seat to the cart and
        checkout with a credit card.

        This test requires 'disable_repeat_order_check' waffle switch turned off on stage, to run.
        - Note: Waffle switch warning copied from existing test without being verified.
        """
        self.verified_seat_payment_with_credit_card(
            selenium,
            is_new_payment_page=True,
            # TODO: restore ADDRESS_US test when it is no longer flaky
            addresses=(ADDRESS_FR,)
        )
