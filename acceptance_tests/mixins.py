import logging
import uuid

from ecommerce_api_client.client import EcommerceApiClient
import requests

from acceptance_tests.api import EnrollmentApiClient
from acceptance_tests.config import (ENABLE_LMS_AUTO_AUTH, APP_SERVER_URL, LMS_PASSWORD, LMS_EMAIL, LMS_URL,
                                     BASIC_AUTH_USERNAME, BASIC_AUTH_PASSWORD, ECOMMERCE_API_SERVER_URL,
                                     LMS_USERNAME, ECOMMERCE_API_TOKEN)
from acceptance_tests.pages import LMSLoginPage, LMSDashboardPage, LMSRegistrationPage

log = logging.getLogger(__name__)


class LmsUserMixin(object):
    password = 'edx'

    def get_lms_user(self):
        if ENABLE_LMS_AUTO_AUTH:
            return self.create_lms_user()

        return LMS_USERNAME, LMS_PASSWORD, LMS_EMAIL

    def generate_user_credentials(self, username_prefix):
        username = username_prefix + uuid.uuid4().hex[0:20]
        password = self.password
        email = '{}@example.com'.format(username)
        return username, email, password

    def create_lms_user(self):
        username, email, password = self.generate_user_credentials(username_prefix='auto_auth_')

        url = '{host}/auto_auth?no_login=true&username={username}&password={password}&email={email}'.format(
            host=LMS_URL, username=username, password=password, email=email)
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

    def login(self):
        self.login_with_lms()

    def login_with_lms(self, email=None, password=None, course_id=None):
        """ Visit LMS and login. """
        email = email or LMS_EMAIL
        password = password or LMS_PASSWORD

        # Note: We use Selenium directly here (as opposed to bok-choy) to avoid issues with promises being broken.
        self.lms_login_page.browser.get(self.lms_login_page.url(course_id))  # pylint: disable=not-callable
        self.lms_login_page.login(email, password)

    def register_via_ui(self, course_id=None):
        """ Creates a new account via the normal user interface. """
        username, email, password = self.generate_user_credentials(username_prefix='otto_acceptance_')
        url = self.lms_registration_page.url(course_id)  # pylint: disable=not-callable
        self.lms_registration_page.browser.get(url)
        self.lms_registration_page.register_and_login(username, username, email, password)

        return username, email, password


class LogoutMixin(object):
    def logout(self):
        url = '{}/accounts/logout/'.format(APP_SERVER_URL)
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
        return EcommerceApiClient(ECOMMERCE_API_SERVER_URL, oauth_access_token=ECOMMERCE_API_TOKEN)

    def assert_order_created_and_completed(self):
        orders = self.ecommerce_api_client.orders.get()['results']
        self.assertGreater(len(orders), 0, 'No orders found for the user!')

        # TODO Validate this is the correct order.
        order = orders[0]

        self.assertEqual(order['status'], 'Complete')


class UnenrollmentMixin(object):
    def tearDown(self):
        self.unenroll_via_dashboard(self.course_id)
        super(UnenrollmentMixin, self).tearDown()

    def unenroll_via_dashboard(self, course_id):
        """ Unenroll the current user from a course via the LMS dashboard. """
        LMSDashboardPage(self.browser).visit()
        self.browser.find_element_by_css_selector('a.action-more').click()
        self.browser.find_element_by_css_selector('a.action-unenroll[data-course-id="{}"]'.format(course_id)).click()
        self.browser.find_element_by_css_selector('#unenroll_form input[name=submit]').click()
