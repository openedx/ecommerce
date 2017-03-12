import abc
import socket
import urllib

from bok_choy.page_object import PageLoadError, PageObject, unguarded
from bok_choy.promise import EmptyPromise
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.support.select import Select

from e2e.config import BASIC_AUTH_PASSWORD, BASIC_AUTH_USERNAME, LMS_URL_ROOT, MARKETING_URL_ROOT
from e2e.pages import submit_lms_login_form


class LMSPage(PageObject):  # pylint: disable=abstract-method
    __metaclass__ = abc.ABCMeta

    def _build_url(self, path):
        url = '{}/{}'.format(LMS_URL_ROOT, path)

        if BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD:
            url = url.replace('://', '://{}:{}@'.format(BASIC_AUTH_USERNAME, BASIC_AUTH_PASSWORD))

        return url

    def _is_browser_on_lms_dashboard(self):
        return self.browser.title.startswith('Dashboard')


class LMSLoginPage(LMSPage):
    def url(self, course_id=None):  # pylint: disable=arguments-differ
        url = self._build_url('login')

        if course_id:
            params = {'enrollment_action': 'enroll', 'course_id': course_id}
            url = '{}?{}'.format(url, urllib.urlencode(params))

        return url

    def is_browser_on_page(self):
        return self.q(css='form#login').visible

    def login(self, email, password):
        submit_lms_login_form(self, email, password)

        # Wait for LMS to redirect to the dashboard
        EmptyPromise(self._is_browser_on_lms_dashboard, "LMS login redirected to dashboard").fulfill()

    @unguarded
    def visit(self, course_id=None):  # pylint: disable=arguments-differ
        url = self.url(course_id)  # pylint: disable=not-callable
        try:
            self.browser.get(url)
        except (WebDriverException, socket.gaierror):
            raise PageLoadError("Could not load page '{!r}' at URL '{}'".format(
                self, url
            ))


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
        EmptyPromise(self._is_browser_on_lms_dashboard, "LMS login redirected to dashboard").fulfill()


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


class LMSLogoutPage(LMSPage):
    @property
    def url(self):
        return self._build_url('logout')

    def is_browser_on_page(self):
        # This page redirects to the marketing site (if available) or the LMS homepage.
        # Check if we are on one of those pages.
        return self.browser.current_url.strip('/') in [MARKETING_URL_ROOT, LMS_URL_ROOT]
