import time


from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.common.exceptions import NoSuchElementException


from e2e.constants import TEST_COURSE_KEY, TEST_COURSE_NAME
from e2e.config import (
    BASIC_AUTH_PASSWORD,
    BASIC_AUTH_USERNAME,
    ECOMMERCE_URL_ROOT,
    LMS_EMAIL,
    LMS_PASSWORD,
    LMS_URL_ROOT
)


class LmsHelpers(object):
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
        form_id = 'login'

        try:
            selenium.find_element_by_css_selector('form#login')
        except NoSuchElementException:
            form_id = 'login-form'

        selenium.find_element_by_css_selector(
            "form#{} input[name='email']".format(form_id)
        ).send_keys(LMS_EMAIL)

        selenium.find_element_by_css_selector(
            "form#{} input[name='password']".format(form_id)
        ).send_keys(LMS_PASSWORD)

        selenium.find_element_by_css_selector(
            'form#{} button.login-button'.format(form_id)
        ).click()

    @staticmethod
    def logout(selenium):
        url = LmsHelpers.build_url('logout')
        selenium.get(url)

    @staticmethod
    def enroll_user(selenium):
        url = LmsHelpers.build_url('courses/{}/course/'.format(TEST_COURSE_KEY))
        selenium.get(url)
        selenium.find_element_by_css_selector('button.enroll-btn').click()


class EcommerceHelpers(object):
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
    def visit_course_page(selenium):
        url = 'courses/{}'.format(TEST_COURSE_KEY)
        selenium.get(EcommerceHelpers.build_url(url))

    @staticmethod
    def assert_on_dashboard(selenium):
        selenium.find_element_by_css_selector('.dashboard')

    @staticmethod
    def submit_new_course_form(selenium):
        assert selenium.find_element_by_css_selector('form.course-form-view').is_displayed()
        selenium.find_element_by_name('id').send_keys(TEST_COURSE_KEY)
        selenium.find_element_by_name('name').send_keys(TEST_COURSE_NAME)
        selenium.find_element_by_css_selector("input[type='radio'][name='type'][value='verified']").click()
        selenium.find_element_by_css_selector("input[type='radio'][name='honor_mode'][value='false']").click()
        selenium.find_element_by_name('expires').send_keys('2050-01-01T00:00:00')
        selenium.find_element_by_name('verification_deadline').send_keys('2050-02-02T00:00:00')
        selenium.find_element_by_name('verification_deadline').clear()
        selenium.find_element_by_name('verification_deadline').send_keys('2050-02-02T00:00:00')
        selenium.find_element_by_css_selector("button[type='submit']").send_keys("\n")

    @staticmethod
    def add_course_to_ecommerce(selenium):
        url = EcommerceHelpers.build_url('courses/new/')
        selenium.get(url)
        EcommerceHelpers.submit_new_course_form(selenium)

        WebDriverWait(selenium, 5).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.course-id"))
        )

