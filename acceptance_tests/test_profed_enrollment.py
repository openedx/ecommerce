from unittest import skip

from bok_choy.web_app_test import WebAppTest

from acceptance_tests.mixins import LogistrationMixin, EnrollmentApiMixin
from acceptance_tests.pages import LMSCourseModePage


@skip('Prof. Ed. tests should be run on an as-needed basis.')
class ProfessionalEducationEnrollmentTests(EnrollmentApiMixin, LogistrationMixin, WebAppTest):
    def test_payment_required(self):
        """ Verify payment is required before enrolling in a professional education course. """

        # Note: Populate this list by querying the course modes/products for prof. ed. course IDs.
        course_ids = ()

        # Sign into LMS
        username, password, email = self.get_lms_user()
        self.login_with_lms(email, password)

        for course_id in course_ids:
            # Visit the course mode page (where auto-enrollment normally occurs)
            LMSCourseModePage(self.browser, course_id).visit()

            # Verify auto-enrollment does NOT occur for the course
            self.assert_user_not_enrolled(username, course_id)
