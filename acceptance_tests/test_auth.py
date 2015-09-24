from unittest import skipUnless

from bok_choy.web_app_test import WebAppTest

from acceptance_tests.config import ENABLE_OAUTH2_TESTS
from acceptance_tests.mixins import LogistrationMixin
from acceptance_tests.pages import DashboardHomePage


@skipUnless(ENABLE_OAUTH2_TESTS, 'OAuth2 tests are not enabled.')
class OAuth2FlowTests(LogistrationMixin, WebAppTest):
    def setUp(self):
        """
        Instantiate the page objects.
        """
        super(OAuth2FlowTests, self).setUp()

        self.app_login_page = DashboardHomePage(self.browser)

    def test_login(self):
        """
        Note: If you are testing locally with a VM and seeing signature expiration errors, ensure the clocks of the VM
        and host are synced within at least one minute (the default signature expiration time) of each other.
        """
        self.login_with_lms()

        # Visit login URL and get redirected
        self.app_login_page.visit()
