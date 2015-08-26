from bok_choy.web_app_test import WebAppTest

from acceptance_tests.config import COURSE_ID
from acceptance_tests.mixins import LogistrationMixin, EcommerceApiMixin, EnrollmentApiMixin, UnenrollmentMixin


class LoginEnrollmentTests(UnenrollmentMixin, EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin, WebAppTest):
    def setUp(self):
        super(LoginEnrollmentTests, self).setUp()
        self.course_id = COURSE_ID
        self.username, self.password, self.email = self.get_lms_user()

    def test_honor_enrollment_and_login(self):
        """ Verifies that a user can login and enroll in a course via the login page. """

        # Login and enroll via LMS
        self.login_with_lms(self.email, self.password, self.course_id)
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id)

    def test_honor_enrollment_and_registration(self):
        """ Verifies that a user can register and enroll in a course via the login page. """
        username, __, __ = self.register_via_ui(self.course_id)
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(username, self.course_id)
