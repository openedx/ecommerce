from unittest import skipUnless

from bok_choy.web_app_test import WebAppTest

from acceptance_tests.config import BULK_PURCHASE_SKU, LMS_EMAIL, LMS_PASSWORD
from acceptance_tests.mixins import (
    EcommerceApiMixin,
    EnrollmentApiMixin,
    LogistrationMixin,
    PaymentMixin
)

from acceptance_tests.pages.basket import BasketPage, BasketAddProductPage


@skipUnless(BULK_PURCHASE_SKU, 'Bulk Purchase SKU not provided, skipping Bulk Purchase tests.')
class BulkPurchaseTests(EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin, PaymentMixin, WebAppTest):

    def setUp(self):
        """ Instantiate the page objects. """
        super(BulkPurchaseTests, self).setUp()
        self.basket_page = BasketPage(self.browser)
        self.basket_add_product_page = BasketAddProductPage(self.browser)

    def test_bulk_purchase(self):
        """
        Verifies that the basket behaves correctly for a "bulk purchase" product
        """
        quantity = 5
        self.login_with_lms(LMS_EMAIL, LMS_PASSWORD)

        self.basket_add_product_page.visit()
        self.assertTrue(self.basket_add_product_page.is_browser_on_page())
        initial_product_subtotal = self.basket_add_product_page.get_product_subtotal()

        self.basket_add_product_page.update_product_quantity(quantity)
        self.assertTrue(self.basket_add_product_page.get_product_quantity(), quantity)

        expected_product_subtotal = initial_product_subtotal * quantity
        updated_product_subtotal = self.basket_add_product_page.get_product_subtotal()
        self.assertEqual(updated_product_subtotal, expected_product_subtotal)
