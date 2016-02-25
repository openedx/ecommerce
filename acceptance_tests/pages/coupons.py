from datetime import date

from acceptance_tests.pages.ecommerce import EcommerceAppPage

from bok_choy.javascript import wait_for_js

from factory.fuzzy import FuzzyText
from selenium.common.exceptions import NoAlertPresentException

from acceptance_tests.config import VERIFIED_COURSE_ID

DEFAULT_START_DATE = date(2015, 1, 1)
DEFAULT_END_DATE = date(2050, 1, 1)


def _get_coupon_name(is_discount):
    """" Returns an appropriate coupon name. """
    prefix = 'test-discount-code-' if is_discount else 'test-enrollment-code-'
    return FuzzyText(length=3, prefix=prefix).fuzz()


class BasketPage(EcommerceAppPage):
    path = 'basket'

    def is_browser_on_page(self):
        return self.browser.title.startswith('Basket')


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
        self.wait_for_element_presence(
            'select[name="seat_type"] option[value="Verified"]',
            'Seat Type Drop-Down List is Present'
        )

        self.q(css="input[name='start_date']").fill(str(DEFAULT_START_DATE))
        self.q(css="input[name='end_date']").fill(str(DEFAULT_END_DATE))
        self.q(css="input[name='client_username']").fill('Test Client')
        self.q(css='select[name="seat_type"] option[value="Verified"]').first.click()

        if is_discount:
            self.q(css='select[name="code_type"] option[value="discount"]').first.click()
            self.wait_for_element_presence('input[name="benefit_value"]', 'Benefit Value Input is Present')
            self.q(css="input[name='benefit_value']").fill('50')

        self.q(css="div.form-actions > button.btn").click()

        self.wait_for_ajax()
        return coupon_name

    @wait_for_js
    def update_coupon_date(self, start_date=DEFAULT_START_DATE, end_date=DEFAULT_END_DATE):
        self.q(css="input[name='start_date']").fill(str(start_date))
        self.q(css="input[name='end_date']").fill(str(end_date))

        self.q(css="div.form-actions > button.btn").click()

        # An alert occurs in firefox here:
        #     This web page is being redirected to a new location.
        #     Would you like to resend the form data you have typed to the new location?
        try:
            self.browser.switch_to_alert().accept()
        except NoAlertPresentException:
            pass

        self.wait_for_ajax()


class CouponsDetailsPage(EcommerceAppPage):
    def is_browser_on_page(self):
        return self.browser.title.endswith('- View Coupon')

    @wait_for_js
    def get_redeem_url(self):
        return self.q(css='table#vouchersTable tbody tr td')[1].text

    @wait_for_js
    def go_to_edit_coupon_form_page(self):
        self.q(css='div.coupon-detail-view div.pull-right a.btn.btn-primary.btn-small').first.click()
        self.wait_for_ajax()


class CouponsListPage(EcommerceAppPage):
    path = 'coupons'

    def is_browser_on_page(self):
        return self.browser.title.startswith('Coupon Codes')

    def create_new_coupon(self):
        self.browser.find_element_by_css_selector('#CreateCoupon').click()
        self.q(
            css='div.coupon-list-view div.page-header h1 div.pull-right a.btn.btn-primary.btn-small'
        ).first.click()
        self.wait_for_ajax()

    @wait_for_js
    def go_to_coupon_details_page(self, coupon_name):
        self.q(css='input[type="search"]').fill(coupon_name)
        self.wait_for_ajax()
        self.q(css='table#couponTable tbody tr td a').first.click()
        self.wait_for_ajax()


class RedeemVoucherPage(EcommerceAppPage):
    def is_browser_on_page(self):
        return self.browser.title.startswith('Redeem')

    @wait_for_js
    def proceed_to_enrollment(self):
        """ Enroll user to a course and redeem voucher code in the process """
        self.q(css='div#offer div.container div.text-right a.btn.btn-primary').first.click()
        self.wait_for_ajax()

    @wait_for_js
    def proceed_to_checkout(self):
        """ Purchase a course and redeem voucher code in the process """
        self.q(css='#offer a.btn-purchase').first.click()
        self.wait_for_ajax()
