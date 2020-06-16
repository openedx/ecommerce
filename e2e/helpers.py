

from e2e.config import (
    BASIC_AUTH_PASSWORD,
    BASIC_AUTH_USERNAME,
    ECOMMERCE_URL_ROOT,
    LMS_EMAIL,
    LMS_PASSWORD,
    LMS_URL_ROOT
)


class LmsHelpers:
    @staticmethod
    def build_url(path):
        url = '{}/{}'.format(LMS_URL_ROOT, path.lstrip('/'))

        if BASIC_AUTH_USERNAME and BASIC_AUTH_PASSWORD:
            url = url.replace('://', '://{}:{}@'.format(BASIC_AUTH_USERNAME, BASIC_AUTH_PASSWORD))

        return url

    @staticmethod
    def login(selenium):
        """ Login to LMS. """
        url = LmsHelpers.build_url('login')
        selenium.get(url)
        LmsHelpers.submit_login_form(selenium)

        # A successful login should redirect to the learner dashboard
        selenium.find_element_by_id('dashboard-main')

    @staticmethod
    def submit_login_form(selenium):
        assert selenium.find_element_by_css_selector('form#login').is_displayed()
        selenium.find_element_by_css_selector('input#login-email').send_keys(LMS_EMAIL)
        selenium.find_element_by_css_selector('input#login-password').send_keys(LMS_PASSWORD)
        selenium.find_element_by_css_selector('button.login-button').click()

    @staticmethod
    def logout(selenium):
        url = LmsHelpers.build_url('logout')
        selenium.get(url)


class EcommerceHelpers:
    @staticmethod
    def build_url(path):
        return '{}/{}'.format(ECOMMERCE_URL_ROOT, path.lstrip('/'))

    @staticmethod
    def logout(selenium):
        url = EcommerceHelpers.build_url('logout/')
        selenium.get(url)

    @staticmethod
    def visit_dashboard(selenium):
        selenium.get(EcommerceHelpers.build_url('dashboard/'))
        EcommerceHelpers.assert_on_dashboard(selenium)

    @staticmethod
    def assert_on_dashboard(selenium):
        selenium.find_element_by_css_selector('.dashboard')
