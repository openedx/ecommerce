import abc
import urllib
from datetime import date

from bok_choy.javascript import wait_for_js
from bok_choy.page_object import PageObject
from bok_choy.promise import EmptyPromise
from factory.fuzzy import FuzzyText
from selenium.common.exceptions import (NoAlertPresentException,
                                        NoSuchElementException)
from selenium.webdriver.support.select import Select

from acceptance_tests.config import (BASIC_AUTH_PASSWORD, BASIC_AUTH_USERNAME,
                                     ECOMMERCE_URL_ROOT, LMS_URL_ROOT,
                                     MARKETING_URL_ROOT, VERIFIED_COURSE_ID)

DEFAULT_START_DATE = date(2015, 1, 1)
DEFAULT_END_DATE = date(2050, 1, 1)


def _get_coupon_name(is_discount):
    """
    Returns an appropriate coupon name.
    """
    prefix = 'test-discount-code-' if is_discount else 'test-enrollment-code-'
    return FuzzyText(length=3, prefix=prefix).fuzz()


class EcommerceAppPage(PageObject):  # pylint: disable=abstract-method
    path = None

    @property
    def url(self):
        return self.page_url

    def __init__(self, browser, path=None):
        super(EcommerceAppPage, self).__init__(browser)
        path = path or self.path
        self.server_url = ECOMMERCE_URL_ROOT
        self.page_url = '{}/{}'.format(self.server_url, path)


class DashboardHomePage(EcommerceAppPage):
    path = 'dashboard'

    def is_browser_on_page(self):
        return self.browser.title.startswith('Dashboard | Oscar')


class BasketPage(EcommerceAppPage):
    path = 'basket'

    def is_browser_on_page(self):
        return self.browser.title.startswith('Basket')


class CouponsCreateEditPage(EcommerceAppPage):
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
        self.browser.execute_script("$('{}')".format(course_id_input))
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
        """
        Enroll user to a course and redeem voucher code in the process
        """
        self.q(css='div#offer div.container div.text-right a.btn.btn-primary').first.click()
        self.wait_for_ajax()

    @wait_for_js
    def proceed_to_checkout(self):
        """
        Purchase a course and redeem voucher code in the process
        """
        self.q(css='#offer a.btn-purchase').first.click()
        self.wait_for_ajax()


class MarketingCourseAboutPage(PageObject):
    def is_browser_on_page(self):
        return self.q(css='.js-enroll-btn').visible

    def _build_url(self, path):
        url = '{}/{}'.format(MARKETING_URL_ROOT, path)

        if BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD:
            url = url.replace('://', '://{}:{}@'.format(BASIC_AUTH_USERNAME, BASIC_AUTH_PASSWORD))

        return url

    @property
    def url(self):
        path = 'course/{}'.format(urllib.quote_plus(self.slug))
        return self._build_url(path)

    def __init__(self, browser, slug):
        super(MarketingCourseAboutPage, self).__init__(browser)
        self.slug = slug


class LMSPage(PageObject):  # pylint: disable=abstract-method
    __metaclass__ = abc.ABCMeta

    def _build_url(self, path):
        url = '{}/{}'.format(LMS_URL_ROOT, path)

        if BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD:
            url = url.replace('://', '://{}:{}@'.format(BASIC_AUTH_USERNAME, BASIC_AUTH_PASSWORD))

        return url

    def _is_browser_on_lms_dashboard(self):
        return lambda: self.browser.title.startswith('Dashboard')


class LMSLoginPage(LMSPage):
    def url(self, course_id=None):  # pylint: disable=arguments-differ
        url = self._build_url('login')

        if course_id:
            params = {'enrollment_action': 'enroll', 'course_id': course_id}
            url = '{}?{}'.format(url, urllib.urlencode(params))

        return url

    def is_browser_on_page(self):
        return self.q(css='form#login').visible

    def login(self, username, password):
        self.q(css='input#login-email').fill(username)
        self.q(css='input#login-password').fill(password)
        self.q(css='button.login-button').click()

        # Wait for LMS to redirect to the dashboard
        EmptyPromise(self._is_browser_on_lms_dashboard(), "LMS login redirected to dashboard").fulfill()


class LMSRegistrationPage(LMSPage):
    def url(self, course_id=None):  # pylint: disable=arguments-differ
        url = self._build_url('register')

        if course_id:
            params = {'enrollment_action': 'enroll', 'course_id': course_id}
            url = '{}?{}'.format(url, urllib.urlencode(params))

        return url

    def is_browser_on_page(self):
        return self.q(css='form#register').visible

    def register_and_login(self, username, name, email, password):
        self.q(css='input#register-username').fill(username)
        self.q(css='input#register-name').fill(name)
        self.q(css='input#register-email').fill(email)
        self.q(css='input#register-password').fill(password)

        try:
            select = Select(self.browser.find_element_by_css_selector('select#register-country'))
            select.select_by_value('US')
        except NoSuchElementException:
            pass

        self.q(css='input#register-honor_code').click()
        self.q(css='button.register-button').click()

        # Wait for LMS to redirect to the dashboard
        EmptyPromise(self._is_browser_on_lms_dashboard(), "LMS login redirected to dashboard").fulfill()


class LMSCourseModePage(LMSPage):
    def is_browser_on_page(self):
        return self.browser.title.lower().startswith('enroll in')

    @property
    def url(self):
        path = 'course_modes/choose/{}/'.format(urllib.quote_plus(self.course_id))
        return self._build_url(path)

    def __init__(self, browser, course_id):
        super(LMSCourseModePage, self).__init__(browser)
        self.course_id = course_id


class LMSDashboardPage(LMSPage):
    @property
    def url(self):
        return self._build_url('dashboard')

    def is_browser_on_page(self):
        return self.browser.title.startswith('Dashboard')
