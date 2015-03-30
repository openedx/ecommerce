from acceptance_tests.config import ENABLE_AUTO_AUTH, APP_SERVER_URL, LMS_PASSWORD, LMS_EMAIL
from acceptance_tests.pages import LMSLoginPage


class LoginMixin(object):
    def setUp(self):
        super(LoginMixin, self).setUp()
        self.lms_login_page = LMSLoginPage(self.browser)

    def login(self):
        if ENABLE_AUTO_AUTH:
            self.login_with_auto_auth()
        else:
            self.login_with_lms()

    def login_with_auto_auth(self):
        url = '{}/test/auto_auth/'.format(APP_SERVER_URL)
        self.browser.get(url)

    def login_with_lms(self, course_id=None):
        """ Visit LMS and login. """

        # Note: We use Selenium directly here (as opposed to Bok Choy) to avoid issues with promises being broken.
        self.lms_login_page.browser.get(self.lms_login_page.url(course_id))  # pylint: disable=not-callable
        self.lms_login_page.login(LMS_EMAIL, LMS_PASSWORD)


class LogoutMixin(object):
    def logout(self):
        url = '{}/accounts/logout/'.format(APP_SERVER_URL)
        self.browser.get(url)
