import abc
import urllib

from bok_choy.page_object import PageObject
from bok_choy.promise import EmptyPromise
from selenium.webdriver.support.select import Select

from acceptance_tests.config import BASIC_AUTH_USERNAME, BASIC_AUTH_PASSWORD, APP_SERVER_URL, LMS_URL


class EcommerceAppPage(PageObject):  # pylint: disable=abstract-method
    path = None

    @property
    def url(self):
        return self.page_url

    def __init__(self, browser, path=None):
        super(EcommerceAppPage, self).__init__(browser)
        path = path or self.path
        self.server_url = APP_SERVER_URL
        self.page_url = '{0}/{1}'.format(self.server_url, path)


class DashboardHomePage(EcommerceAppPage):
    path = ''

    def is_browser_on_page(self):
        return self.browser.title.startswith('Dashboard | Oscar')


class LMSPage(PageObject):  # pylint: disable=abstract-method
    __metaclass__ = abc.ABCMeta

    def _build_url(self, path):
        url = '{0}/{1}'.format(LMS_URL, path)

        if BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD:
            url = url.replace('://', '://{0}:{1}@'.format(BASIC_AUTH_USERNAME, BASIC_AUTH_PASSWORD))

        return url


class LMSLoginPage(LMSPage):
    def url(self, course_id=None):  # pylint: disable=arguments-differ
        url = self._build_url('login')

        if course_id:
            params = {'enrollment_action': 'enroll', 'course_id': course_id}
            url = '{0}?{1}'.format(url, urllib.urlencode(params))

        return url

    def is_browser_on_page(self):
        return self.browser.title.startswith('Sign in')

    def _is_browser_on_lms_dashboard(self):
        return lambda: self.browser.title.startswith('Dashboard')

    def login(self, username, password):
        self.q(css='input#login-email').fill(username)
        self.q(css='input#login-password').fill(password)
        self.q(css='button.login-button').click()

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

    def purchase_verified(self):
        # Click the purchase button on the track selection page
        self.q(css='input[name=verified_mode]').click()

        # Click the payment button
        self.q(css='a#cybersource').click()

        # Wait for form to load
        self.wait_for_element_presence('#billing_details', 'Waiting for billing form to load.')

        # Select the credit card type (Visa) first since it triggers the display of additional fields
        self.q(css='#card_type_001').click()  # Visa

        # Select the appropriate <option> elements
        select_fields = (
            ('#bill_to_address_country', 'US'),
            ('#bill_to_address_state_us_ca', 'MA'),
            ('#card_expiry_year', '2020')
        )
        for selector, value in select_fields:
            select = Select(self.browser.find_element_by_css_selector(selector))
            select.select_by_value(value)

        # Fill in the text fields
        billing_information = {
            'bill_to_forename': 'Ed',
            'bill_to_surname': 'Xavier',
            'bill_to_address_line1': '141 Portland Ave.',
            'bill_to_address_line2': '9th Floor',
            'bill_to_address_city': 'Cambridge',
            'bill_to_address_postal_code': '02141',
            'bill_to_email': 'edx@example.com',
            'card_number': '4111111111111111',
            'card_cvn': '1234'
        }

        for field, value in billing_information.items():
            self.q(css='#' + field).fill(value)

        # Click the payment button
        self.q(css='input[type=submit]').click()
