from datetime import date
from unittest import skipUnless

from bok_choy.web_app_test import WebAppTest

from e2e.config import ENABLE_COUPON_ADMIN_TESTS
from e2e.constants import DEFAULT_END_DATE, DEFAULT_START_DATE
from e2e.mixins import CouponMixin, LogistrationMixin
from e2e.pages.coupons import CouponsCreatePage, CouponsDetailsPage, CouponsListPage


@skipUnless(ENABLE_COUPON_ADMIN_TESTS, 'Coupon admin tests are disabled.')
class CouponAdministrationTests(CouponMixin, LogistrationMixin, WebAppTest):
    def setUp(self):
        """ Instantiate the page objects. """
        super(CouponAdministrationTests, self).setUp()

        self.coupons_create_edit_page = CouponsCreatePage(self.browser)
        self.coupons_details_page = CouponsDetailsPage(self.browser)
        self.coupons_list_page = CouponsListPage(self.browser)
        self.login_with_lms()

    def create_coupon(self):
        """ Create a coupon via UI. """
        # Verify we reach the coupons list page.
        self.coupons_list_page.visit()
        self.assertTrue(self.coupons_list_page.is_browser_on_page())
        self.coupons_list_page.create_new_coupon()

        # Verify we reach the coupons create / edit page.
        self.assertTrue(self.coupons_create_edit_page.is_browser_on_page())

        self.coupons_create_edit_page.fill_create_coupon_form(is_discount=False)

        # Verify we reach the coupons details page.
        self.assertTrue(self.coupons_details_page.is_browser_on_page())

    def assert_coupon_dates(self, expected_start_date, expected_end_date):
        """ Assert the start/end dates displayed to the user match the expected dates. """
        start_date = self.browser.find_elements_by_css_selector(
            'div.coupon-detail-view div.start-date-info div.value'
        )[0].text
        end_date = self.browser.find_elements_by_css_selector(
            'div.coupon-detail-view div.end-date-info div.value'
        )[0].text

        self.assertEqual(start_date, expected_start_date.strftime('%m/%d/%Y %I:%M %p'))
        self.assertEqual(end_date, expected_end_date.strftime('%m/%d/%Y %I:%M %p'))

    def test_create_coupon(self):
        """ Test creating a new coupon. """
        self.create_coupon()

    def test_update_coupon_dates(self):
        """ Test updating the dates on a coupon. """
        self.create_coupon()
        self.assert_coupon_dates(DEFAULT_START_DATE, DEFAULT_END_DATE)

        self.coupons_details_page.go_to_edit_coupon_form_page()
        self.assertTrue(self.coupons_create_edit_page.is_browser_on_page())

        future_start_date = date(3000, 1, 1)
        future_end_date = date(4000, 1, 1)

        self.coupons_create_edit_page.update_coupon_date(start_date=future_start_date, end_date=future_end_date)
        self.assertTrue(self.coupons_details_page.is_browser_on_page())
        self.assert_coupon_dates(future_start_date, future_end_date)
