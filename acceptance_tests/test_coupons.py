from unittest import skipUnless

from bok_choy.web_app_test import WebAppTest

from acceptance_tests.config import ENABLE_OAUTH2_TESTS
from acceptance_tests.mixins import LogistrationMixin
from acceptance_tests.pages import CouponsCreateEditPage, CouponsDetailsPage, CouponsListPage


@skipUnless(ENABLE_OAUTH2_TESTS, 'OAuth2 tests are not enabled.')
class CouponsFlowTests(LogistrationMixin, WebAppTest):
    def setUp(self):
        """
        Instantiate the page objects.
        """
        super(CouponsFlowTests, self).setUp()

        self.coupons_create_edit_page = CouponsCreateEditPage(self.browser)
        self.coupons_details_page = CouponsDetailsPage(self.browser)
        self.coupons_list_page = CouponsListPage(self.browser)
        self.login_with_lms()

    def test_listcoupons(self):
        """ Test listing the existing coupons. """
        # Visit coupons list page
        self.coupons_list_page.visit()

        # Verify we reach the coupons list page.
        self.assertTrue(self.coupons_list_page.is_browser_on_page())
        self.coupons_list_page.create_new_coupon()

        # Verify we reach the coupons create / edit page.
        self.assertTrue(self.coupons_create_edit_page.is_browser_on_page())

        self.coupons_create_edit_page.fill_create_coupon_form(is_discount=False)

        # Verify we reach the coupons details page.
        self.assertTrue(self.coupons_details_page.is_browser_on_page())
