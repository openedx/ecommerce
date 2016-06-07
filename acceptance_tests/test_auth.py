from unittest import skipUnless

from bok_choy.web_app_test import WebAppTest

from acceptance_tests.config import ENABLE_SSO_TESTS, MARKETING_URL_ROOT, LMS_URL_ROOT
from acceptance_tests.mixins import LogistrationMixin, LogoutMixin, LMSLogoutMixin
from acceptance_tests.pages import DashboardHomePage


@skipUnless(ENABLE_SSO_TESTS, 'Single sign-on tests are not enabled.')
class SingleSignOnTests(LogistrationMixin, LogoutMixin, LMSLogoutMixin, WebAppTest):
    def setUp(self):
        """ Instantiate the page objects. """
        super(SingleSignOnTests, self).setUp()
        self.otto_dashboard_page = DashboardHomePage(self.browser)

    def test_login_and_logout(self):
        """
        Note: If you are testing locally with a VM and seeing signature expiration errors, ensure the clocks of the VM
        and host are synced within at least one minute (the default signature expiration time) of each other.
        """
        self.login_with_lms()

        # Visit the Otto dashboard to trigger an OpenID Connect login
        self.otto_dashboard_page.visit()

        # Logging out of Otto should redirect the user to the LMS logout page, which redirects
        # to the marketing site (if available) or the LMS homepage.
        self.logout_via_otto()
        self.assertIn(self.browser.current_url.strip('/'), [MARKETING_URL_ROOT, LMS_URL_ROOT])

    def test_lms_logout(self):
        """ Verify that logging out of the LMS also logs the user out of Otto. """
        self.login_with_lms()
        self.otto_dashboard_page.visit()
        self.logout_via_lms()

        # Now that the user has been logged out, navigating to the dashboard should result in the user being
        # redirected to the LMS login page. This indicates the user has been logged out of both LMS and Otto.
        # Since the user is logged out, calling otto_dashboard_page.visit() will timeout. This is due to the fact that
        # visit() expects the browser to be on the actual dashboard page. We are accessing the page directly
        # to avoid this issue.
        self.browser.get(self.otto_dashboard_page.url)
        self.assertTrue(self.lms_login_page.is_browser_on_page())
