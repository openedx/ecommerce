from unittest import skipUnless

from bok_choy.web_app_test import WebAppTest
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from e2e.config import MARKETING_URL_ROOT, PROFESSIONAL_COURSE_ID
from e2e.mixins import EnrollmentApiMixin, LogistrationMixin
from e2e.pages.lms import LMSCourseModePage
from e2e.pages.marketing import MarketingCourseAboutPage


@skipUnless(PROFESSIONAL_COURSE_ID, 'Professional education tests are not enabled.')
class ProfessionalEducationEnrollmentTests(EnrollmentApiMixin, LogistrationMixin, WebAppTest):
    def test_payment_required(self):
        """Verify payment is required before enrolling in a professional education course."""
        username, password, email = self.get_lms_user()
        self.login_with_lms(email, password)

        if MARKETING_URL_ROOT:
            course_about_page = MarketingCourseAboutPage(self.browser, PROFESSIONAL_COURSE_ID)
            course_about_page.visit()

            # Click the first enroll button on the page to take the browser to the track selection page,
            # and allow it to load.
            course_about_page.q(css='.js-enroll-btn').first.click()
            WebDriverWait(self.browser, 10).until(EC.presence_of_element_located((By.CLASS_NAME, 'basket')))
        else:
            # Visit the course mode page (where auto-enrollment normally occurs)
            LMSCourseModePage(self.browser, PROFESSIONAL_COURSE_ID).visit()

        # Verify auto-enrollment does NOT occur for the course.
        self.assert_user_not_enrolled(username, PROFESSIONAL_COURSE_ID)
