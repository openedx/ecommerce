import random
# The string module is not deprecated. This is a bug in Pylint: https://www.logilab.org/ticket/2481.
import string  # pylint: disable=deprecated-module

from bok_choy.javascript import wait_for_js
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait

from e2e.config import ECOMMERCE_URL_ROOT, VERIFIED_COURSE_ID
from e2e.constants import CODE, DEFAULT_END_DATE, DEFAULT_START_DATE
from e2e.expected_conditions import option_selected
from e2e.pages.ecommerce import EcommerceAppPage


def _get_coupon_name(is_discount):
    """ Returns an appropriate coupon name. """
    prefix = 'test-discount-code-' if is_discount else 'test-enrollment-code-'
    suffix = ''.join(random.choice(string.ascii_letters) for _ in range(10))

    return prefix + suffix


class CouponsCreatePage(EcommerceAppPage):
    path = 'coupons/new'

    def is_browser_on_page(self):
        return self.q(css='form.coupon-form-view').visible

    @wait_for_js
    def fill_create_coupon_form(self, is_discount):
        """ Fills the coupon form with test data and creates the coupon.

        Args:
            is_discount(bool): Indicates if the code that's going to be created
                               should be a discount or enrollment coupon code.

        Returns:
            coupon_name(str): Fuzzied name of the coupon that has been created.

        """
        course_id_input = 'input[name="course_id"]'
        coupon_name = _get_coupon_name(is_discount)
        self.q(css='input[name="title"]').fill(coupon_name)
        self.q(css=course_id_input).fill(VERIFIED_COURSE_ID)
        self.wait_for_ajax()

        wait = WebDriverWait(self.browser, 2)
        verified_option_present = EC.presence_of_element_located(
            (By.CSS_SELECTOR, 'select[name="seat_type"] option[value="Verified"]')
        )
        wait.until(verified_option_present)

        self.q(css="input[name='start_date']").fill(str(DEFAULT_START_DATE))
        self.q(css="input[name='end_date']").fill(str(DEFAULT_END_DATE))
        self.q(css="input[name='client']").fill('Test Client')

        select = Select(self.browser.find_element_by_css_selector('select[name="seat_type"]'))
        select.select_by_value('Verified')

        # Prevent the test from advancing before the seat type is selected.
        wait = WebDriverWait(self.browser, 2)
        verified_option_selected = option_selected(select, 'Verified')
        wait.until(verified_option_selected)

        select = Select(self.browser.find_element_by_css_selector('select[name="code_type"]'))
        select.select_by_value('Discount code')

        wait = WebDriverWait(self.browser, 2)
        benefit_input_present = EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="benefit_value"]'))
        wait.until(benefit_input_present)

        self.q(css="input[name='code']").fill(CODE)

        if is_discount:
            self.q(css="input[name='benefit_value']").fill('50')
        else:
            self.q(css="input[name='benefit_value']").fill('100')

        self.q(css="input[name='invoice_number']").fill('1001')
        self.q(css="input[name='invoice_payment_date']").fill(str(DEFAULT_END_DATE))
        self.q(css="input[name='price']").fill('100')

        self.q(css="div.form-actions > button.btn").click()

        self.wait_for_ajax()
        return coupon_name

    @wait_for_js
    def update_coupon_date(self, start_date=DEFAULT_START_DATE, end_date=DEFAULT_END_DATE):
        self.q(css="input[name='start_date']").fill(str(start_date))
        self.q(css="input[name='end_date']").fill(str(end_date))

        self.q(css="div.form-actions > button.btn").click()
        self.wait_for_ajax()


class CouponsDetailsPage(EcommerceAppPage):
    def is_browser_on_page(self):
        return self.browser.title.endswith('- View Coupon')

    @wait_for_js
    def get_redeem_url(self, code):
        return '{}/coupons/offer/?code={}'.format(ECOMMERCE_URL_ROOT, code)

    @wait_for_js
    def go_to_edit_coupon_form_page(self):
        self.browser.find_element_by_id('CouponEdit').click()
        self.wait_for_ajax()


class CouponsListPage(EcommerceAppPage):
    path = 'coupons'

    def is_browser_on_page(self):
        return self.browser.title.startswith('Coupon Codes')

    @wait_for_js
    def create_new_coupon(self):
        # Wait for the coupon list page to load.
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.ID, 'CreateCoupon'))
        )
        self.browser.find_element_by_id('CreateCoupon').click()

    @wait_for_js
    def go_to_coupon_details_page(self, coupon_name):
        self.q(css='input[type="search"]').fill(coupon_name)
        self.wait_for_ajax()
        self.browser.find_element_by_id('couponTable').first.click()
        self.wait_for_ajax()


class RedeemVoucherPage(EcommerceAppPage):
    def is_browser_on_page(self):
        return self.browser.title.startswith('Redeem')

    @wait_for_js
    def proceed_to_enrollment(self):
        """ Enroll user to a course and redeem voucher code in the process """
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.ID, 'RedeemEnrollment'))
        )
        self.browser.find_element_by_id('RedeemEnrollment').click()
        self.wait_for_ajax()

    @wait_for_js
    def proceed_to_checkout(self):
        """ Purchase a course and redeem voucher code in the process """
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.ID, 'PurchaseCertificate'))
        )
        self.browser.find_element_by_id('PurchaseCertificate').click()
        self.wait_for_ajax()
