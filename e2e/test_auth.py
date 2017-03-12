from unittest import skipUnless

from bok_choy.promise import EmptyPromise
from bok_choy.web_app_test import WebAppTest

from e2e.config import ENABLE_SSO_TESTS, LMS_URL_ROOT, MARKETING_URL_ROOT
from e2e.mixins import LMSLogoutMixin, LogistrationMixin, OttoAuthenticationMixin
from e2e.pages.ecommerce import EcommerceDashboardHomePage


@skipUnless(ENABLE_SSO_TESTS, 'Single sign-on tests are not enabled.')
class SingleSignOnTests(LogistrationMixin, OttoAuthenticationMixin, LMSLogoutMixin, WebAppTest):
    def setUp(self):
        """ Instantiate the page objects. """
        super(SingleSignOnTests, self).setUp()
        self.otto_dashboard_page = EcommerceDashboardHomePage(self.browser)

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

    def test_login_redirection(self):
        """ Verify the user is redirected to the Otto dashboard after logging in. """
        self.login_via_otto()
        promise_description = "Ensure redirect to Otto dashboard after login."
        EmptyPromise(self.otto_dashboard_page.is_browser_on_page, promise_description).fulfill()
