from unittest import skipUnless

from bok_choy.web_app_test import WebAppTest

from e2e.config import BULK_PURCHASE_SKU, LMS_EMAIL, LMS_PASSWORD
from e2e.mixins import EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin, PaymentMixin
from e2e.pages.basket import BasketAddProductPage, BasketPage


@skipUnless(BULK_PURCHASE_SKU, 'Bulk Purchase SKU not provided, skipping Bulk Purchase tests.')
class BulkPurchaseTests(EcommerceApiMixin, EnrollmentApiMixin, LogistrationMixin, PaymentMixin, WebAppTest):

    def setUp(self):
        """ Instantiate the page objects. """
        super(BulkPurchaseTests, self).setUp()
        self.basket_page = BasketPage(self.browser)
        self.basket_add_product_page = BasketAddProductPage(self.browser)

    def _update_course_quantity(self, quantity):
        """ Update the course quantity in basket for bulk purchase. """
        self.basket_add_product_page.update_product_quantity(quantity)
        self.assertTrue(self.basket_add_product_page.get_product_quantity(), quantity)

    def _verify_course_total(self, expected_product_subtotal):
        """ Verify the course total in basket for bulk purchase. """
        updated_product_subtotal = self.basket_add_product_page.get_product_subtotal()
        self.assertEqual(updated_product_subtotal, expected_product_subtotal)

    def test_quantity_update_for_bulk_purchase(self):
        """
        Verifies that the quantity and total price updates correctly for bulk purchase
        """
        self.login_with_lms(LMS_EMAIL, LMS_PASSWORD)
        self.basket_add_product_page.visit()
        self.assertTrue(self.basket_add_product_page.is_browser_on_page())
        initial_product_subtotal = self.basket_add_product_page.get_product_subtotal()

        quantity = 5
        self._update_course_quantity(quantity)
        expected_product_subtotal = initial_product_subtotal * quantity
        self._verify_course_total(expected_product_subtotal)

        quantity = 1
        self._update_course_quantity(quantity)
        expected_product_subtotal = initial_product_subtotal * quantity
        self._verify_course_total(expected_product_subtotal)

        quantity = 4
        self._update_course_quantity(quantity)
        expected_product_subtotal = initial_product_subtotal * quantity
        self._verify_course_total(expected_product_subtotal)

    def test_quantity_update_message_for_bulk_purchase(self):
        """
        Verifies that the basket does not show success message for updating quantity for bulk purchase
        """
        self.login_with_lms(LMS_EMAIL, LMS_PASSWORD)
        self.basket_add_product_page.visit()
        self.assertTrue(self.basket_add_product_page.is_browser_on_page())
        initial_product_subtotal = self.basket_add_product_page.get_product_subtotal()

        quantity = 5
        self._update_course_quantity(quantity)
        expected_product_subtotal = initial_product_subtotal * quantity
        self._verify_course_total(expected_product_subtotal)
        self.assertFalse(self.basket_add_product_page.q(css='div#messages').is_present())

    def test_course_detail(self):
        """
        Verifies that the basket displays course details correctly
        """
        self.login_with_lms(LMS_EMAIL, LMS_PASSWORD)

        self.basket_add_product_page.visit()
        self.assertTrue(self.basket_add_product_page.is_browser_on_page())
        self.assertTrue(self.basket_add_product_page.q(css='p.course_name').is_present())
        self.assertTrue(self.basket_add_product_page.q(css='p.course_description').is_present())
        self.assertTrue(self.basket_add_product_page.q(css='div.course_image img.thumbnail').is_present())
        self.assertTrue(self.basket_add_product_page.q(css='label.course-price-label').is_present())
        self.assertTrue(self.basket_add_product_page.q(css='input.quantity[min="1"]').is_present())
        self.assertTrue(self.basket_add_product_page.q(css='button.update-button').is_present())
        self.assertTrue(self.basket_add_product_page.q(css='div.price').is_present())

    def test_add_coupon_link(self):
        """
        Verifies that the basket does not have coupons for bulk purchase seat
        """
        self.login_with_lms(LMS_EMAIL, LMS_PASSWORD)

        self.basket_add_product_page.visit()
        self.assertTrue(self.basket_add_product_page.is_browser_on_page())
        self.assertFalse(self.basket_add_product_page.q(css='p#voucher_form_link a').is_present())

    def test_basket_switch_link(self):
        """
        Verifies that the basket has the link to switch the basket view to single seat purchase
        """
        self.login_with_lms(LMS_EMAIL, LMS_PASSWORD)

        self.basket_add_product_page.visit()
        self.assertTrue(self.basket_add_product_page.is_browser_on_page())

        link_text = self.basket_add_product_page.q(css='div.basket-switch-link a.btn-link')[0].text
        self.assertEqual(u"Click here to just purchase an enrollment for yourself", link_text)

    def test_basket_payment_buttons(self):
        """
        Verifies that the basket has the payment buttons for paypal and cybersource
        """
        self.login_with_lms(LMS_EMAIL, LMS_PASSWORD)

        self.basket_add_product_page.visit()
        self.assertTrue(self.basket_add_product_page.is_browser_on_page())

        self.assertTrue(self.basket_add_product_page.q(css='button#cybersource').is_present())
        self.assertTrue(self.basket_add_product_page.q(css='button#paypal').is_present())
