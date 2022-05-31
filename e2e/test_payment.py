

import datetime
import logging
import time

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.wait import WebDriverWait

from e2e.api import DiscoveryApi, EcommerceApi, EnrollmentApi
from e2e.config import LMS_USERNAME
# from e2e.constants import ADDRESS_FR, ADDRESS_US  # Can uncomment when associated test below is ready (REV-2624)
from e2e.helpers import EcommerceHelpers, LmsHelpers

log = logging.getLogger(__name__)


class TestSeatPayment:
    def checkout_with_credit_card(self, selenium, address):
        """
        Submits the credit card form hosted by the E-Commerce Service.
        """
        billing_information = {
            'firstName': 'Ed',
            'lastName': 'Xavier',
            'address': address['line1'],
            'unit': address['line2'],
            'city': address['city'],
            'postalCode': address['postal_code'],
            # 'cardNumber': '4111111111111111',
            # 'securityCode': '123'
        }

        flex_microform_information = {
            'cardNumber': ('number', '4111111111111111'),
            'securityCode': ('securityCode', '123'),
        }

        country = address['country']
        state = address['state'] or ''

        card_expiry_year = str(datetime.datetime.now().year + 3)
        select_fields = [
            (By.ID, 'country', country),
            (By.ID, 'cardExpirationMonth', '12'),
            (By.ID, 'cardExpirationYear', card_expiry_year),
        ]

        if country in ('US', 'CA',):
            # Ensure the state field has switched from a text to a select field for certain countries
            select_fields.append((By.XPATH, ".//label[@for='state']/following-sibling::select", state))
        else:
            billing_information['state'] = state

        # Select the appropriate <option> elements
        for locator_type, selector, value in select_fields:
            if value:
                try:
                    # form fields are initially disabled
                    element = WebDriverWait(selenium, 10).until(
                        EC.element_to_be_clickable((locator_type, selector))
                    )
                except:
                    raise Exception('Timeout exception with locator (%s, %s).' % (locator_type, selector))   # pylint: disable=raise-missing-from

                select = Select(element)
                select.select_by_value(value)

        # Fill in the text fields
        for field, value in billing_information.items():
            selenium.find_element_by_id(field).send_keys(value)

        for field, (microform_field_name, value) in flex_microform_information.items():
            selenium.switch_to.frame(
                selenium.find_element_by_id(field).find_element_by_tag_name('iframe')
            )
            selenium.find_element_by_name(microform_field_name).send_keys(value)
            selenium.switch_to.parent_frame()

        # Click the payment button
        selenium.find_element_by_id('placeOrderButton').click()

    def assert_browser_on_receipt_page(self, selenium):
        WebDriverWait(selenium, 20).until(
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

    def add_item_to_basket(self, selenium, sku):
        page_css_selector = ".page__payment"

        # Add the item to the basket and start the checkout process
        selenium.get(EcommerceHelpers.build_url(
            '/basket/add/?sku={}'.format(
                sku,
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

    def verified_seat_payment_with_credit_card(self, selenium, addresses):
        """
        Validates users can add a verified seat to the cart and checkout with a credit card.

        Arguments:
            addresses (tuple): Addresses to test.

        This test requires 'disable_repeat_order_check' waffle switch turned off on stage, to run.

        """
        LmsHelpers.login(selenium)
        discovery_client = DiscoveryApi()

        # REV-2189: The course runs we get back may not exist in ecommerce, or may not be able to be added to the
        # basket (ex: upgrade time expired). We can't easily make that determination here, so we try this in a loop
        # until we find one that works. This quick fix is made in the hope that this whole system is deprecated in the
        # near future.
        course_runs = discovery_client.get_course_runs('verified')

        assert len(course_runs) > 0

        # Use this to make sure that the tests actually ran and that we didn't accidentally skip it due to
        # not finding a valid seat.
        test_run_successfully = False

        # Check up to 10 course runs to find a good one
        for potential_course_run in course_runs[:10]:
            course_run = discovery_client.get_course_run(potential_course_run['key'])
            verified_seat = self.get_verified_seat(course_run)
            try:
                for address in addresses:
                    # This is the line that will throw the TimeoutException if the sku isn't valid
                    # for this test.
                    self.add_item_to_basket(selenium, verified_seat['sku'])
                    log.warning("%s, was added to the basket.", verified_seat['sku'])
                    self.checkout_with_credit_card(selenium, address)
                    self.assert_browser_on_receipt_page(selenium)

                    course_run_key = course_run['key']
                    self.assert_user_enrolled_in_course_run(LMS_USERNAME, course_run_key)
                    assert self.refund_orders_for_course_run(course_run_key)

                test_run_successfully = True

                # We finished a test, stop trying course runs
                break
            except TimeoutException as exc:
                # We only want to continue on this particular error from add_item_to_basket.
                if "No product is available" in exc.msg:
                    log.warning("Failed to get a valid course run for SKU %s, continuing. ", verified_seat['sku'])
                else:  # TODO: Remove else clause after investigation (REV-2493)
                    log.warning("Failed to add basket line for SKU %s, continuing", verified_seat['sku'])
                    log.warning("exc.msg was: %s", exc.msg)
                continue

        assert test_run_successfully, "Unable to find a valid course run to test!"

    #  @FIXME: Commenting out test, pending necessary updates in REV-2624 for it to work again
    # def test_verified_seat_payment_with_credit_card_payment_page(self, selenium):
    #     """
    #     Using the payment microfrontend page, validates users can add a verified seat to the cart and
    #     checkout with a credit card.

    #     This test requires 'disable_repeat_order_check' waffle switch turned off on stage, to run.
    #     - Note: Waffle switch warning copied from original basket page test without being verified.
    #     """
    #     self.verified_seat_payment_with_credit_card(
    #         selenium,
    #         addresses=(ADDRESS_US, ADDRESS_FR,)
    #     )
