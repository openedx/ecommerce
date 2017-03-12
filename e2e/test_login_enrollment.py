from bok_choy.web_app_test import WebAppTest

from e2e.config import HONOR_COURSE_ID
from e2e.mixins import EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin, UnenrollmentMixin


class LoginEnrollmentTests(UnenrollmentMixin, EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin, WebAppTest):
    def setUp(self):
        super(LoginEnrollmentTests, self).setUp()
        self.course_id = HONOR_COURSE_ID
        self.username, self.password, self.email = self.get_lms_user()

    def test_honor_enrollment_and_login(self):
        """Verify that a user can enroll in a course while logging in.

        Also verifies that the login page redirects the user to their dashboard
        following enrollment. At the time of writing, the login page only redirects
        to the dashboard when the user has enrolled in an honor-only course. Otherwise,
        the user is redirected to a track selection or payment interstitial.
        """
        # Login and enroll via LMS
        self.login_with_lms(self.email, self.password, self.course_id)
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(self.username, self.course_id)

    def test_honor_enrollment_and_registration(self):
        """Verify that a user can enroll in a course while registering.

        Also verifies that the registration page redirects the user to their dashboard
        following enrollment. At the time of writing, the registration page only redirects
        to the dashboard when the user has enrolled in an honor-only course. Otherwise,
        the user is redirected to a track selection or payment interstitial.
        """
        username, __, __ = self.register_via_ui(self.course_id)
        self.assert_order_created_and_completed()
        self.assert_user_enrolled(username, self.course_id)
