from unittest import skipUnless

from bok_choy.web_app_test import WebAppTest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from acceptance_tests.config import ECOMMERCE_URL_ROOT, PROFESSIONAL_COURSE_ID, MARKETING_URL_ROOT
from acceptance_tests.mixins import LogistrationMixin, EnrollmentApiMixin
from acceptance_tests.pages.lms import LMSCourseAboutPage
from acceptance_tests.pages.marketing import MarketingCourseAboutPage


@skipUnless(PROFESSIONAL_COURSE_ID, 'Professional education tests are not enabled.')
class ProfessionalEducationEnrollmentTests(EnrollmentApiMixin, LogistrationMixin, WebAppTest):
    def test_payment_required(self):
        """Verify payment is required before enrolling in a professional education course."""
        __, password, email = self.get_lms_user()
        self.login_with_lms(email, password)
        on_basket_page = EC.presence_of_element_located((By.CLASS_NAME, 'basket'))

        if MARKETING_URL_ROOT:
            course_about_page = MarketingCourseAboutPage(self.browser, PROFESSIONAL_COURSE_ID)
            course_about_page.visit()

            # Click the first enroll button on the page to take the browser to the track selection page,
            # and allow it to load.
            course_about_page.q(css='.js-enroll-btn').first.click()
            WebDriverWait(self.browser, 10).until(on_basket_page)
        else:
            # Clicking on the enroll button the user gets redirected to the ecommerce basket.
            ecommerce_url = '{}/basket/'.format(ECOMMERCE_URL_ROOT)
            lms_course_page = LMSCourseAboutPage(self.browser, PROFESSIONAL_COURSE_ID).visit()
            lms_course_page.q(css='.add-to-cart').click()

            WebDriverWait(self.browser, 10).until(on_basket_page)
            self.assertEqual(self.browser.current_url, ecommerce_url)
