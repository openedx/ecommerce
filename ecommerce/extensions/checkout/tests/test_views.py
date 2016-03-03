from decimal import Decimal

from django.core.urlresolvers import reverse
from django.conf import settings
import ddt
import httpretty
from oscar.core.loading import get_model
from oscar.test import newfactories as factories

from ecommerce.core.tests import toggle_switch
from ecommerce.core.url_utils import get_ecommerce_url, get_lms_url
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.tests.testcases import TestCase

Order = get_model('order', 'Order')


class FreeCheckoutViewTests(TestCase):
    """ FreeCheckoutView view tests. """
    path = reverse('checkout:free-checkout')

    def setUp(self):
        super(FreeCheckoutViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        toggle_switch('otto_receipt_page', True)

    def prepare_basket(self, price):
        """ Helper function that creates a basket and adds a product with set price to it. """
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        basket.add_product(factories.ProductFactory(stockrecords__price_excl_tax=price), 1)
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.total_incl_tax, Decimal(price))

    def test_empty_basket(self):
        """ Verify redirect to basket summary in case of empty basket. """
        response = self.client.get(self.path)
        expected_url = self.get_full_url(reverse('basket:summary'))
        self.assertRedirects(response, expected_url)

    def test_non_free_basket(self):
        """ Verify an exception is raised when the URL is being accessed to with a non-free basket. """
        self.prepare_basket(10)

        with self.assertRaises(BasketNotFreeError):
            self.client.get(self.path)

    @httpretty.activate
    def test_successful_redirect(self):
        """ Verify redirect to the receipt page. """
        self.prepare_basket(0)
        self.assertEqual(Order.objects.count(), 0)
        receipt_page = get_ecommerce_url(settings.RECEIPT_PAGE_PATH)

        response = self.client.get(self.path)
        self.assertEqual(Order.objects.count(), 1)

        expected_url = '{}?order_number={}'.format(receipt_page, Order.objects.first().number)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @httpretty.activate
    def test_redirect_to_lms_receipt(self):
        """ Verify that disabling the otto_receipt_page switch redirects to the LMS receipt page. """
        toggle_switch('otto_receipt_page', False)
        self.prepare_basket(0)
        self.assertEqual(Order.objects.count(), 0)
        receipt_page = get_lms_url('/commerce/checkout/receipt')

        response = self.client.get(self.path)
        self.assertEqual(Order.objects.count(), 1)

        expected_url = '{}?orderNum={}'.format(receipt_page, Order.objects.first().number)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)


class CancelCheckoutViewTests(TestCase):
    """ CancelCheckoutView view tests. """

    path = reverse('checkout:cancel-checkout')

    def setUp(self):
        super(CancelCheckoutViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    @httpretty.activate
    def test_get_returns_payment_support_email_in_context(self):
        """
        Verify that after receiving a GET response, the view returns a payment support email in its context.
        """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['payment_support_email'], self.request.site.siteconfiguration.payment_support_email
        )

    @httpretty.activate
    def test_post_returns_payment_support_email_in_context(self):
        """
        Verify that after receiving a POST response, the view returns a payment support email in its context.
        """
        post_data = {'decision': 'CANCEL', 'reason_code': '200', 'signed_field_names': 'dummy'}
        response = self.client.post(self.path, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['payment_support_email'], self.request.site.siteconfiguration.payment_support_email
        )


class CheckoutErrorViewTests(TestCase):
    """ CheckoutErrorView view tests. """

    path = reverse('checkout:error')

    def setUp(self):
        super(CheckoutErrorViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    @httpretty.activate
    def test_get_returns_payment_support_email_in_context(self):
        """
        Verify that after receiving a GET response, the view returns a payment support email in its context.
        """
        response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['payment_support_email'], self.request.site.siteconfiguration.payment_support_email
        )

    @httpretty.activate
    def test_post_returns_payment_support_email_in_context(self):
        """
        Verify that after receiving a POST response, the view returns a payment support email in its context.
        """
        post_data = {'decision': 'CANCEL', 'reason_code': '200', 'signed_field_names': 'dummy'}
        response = self.client.post(self.path, data=post_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['payment_support_email'], self.request.site.siteconfiguration.payment_support_email
        )


@ddt.ddt
class ReceiptViewTests(TestCase):
    """
    Tests for the receipt view.
    """

    path = reverse('checkout:receipt')

    def setUp(self):
        super(ReceiptViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)

    def test_login_required(self):
        """ The view should redirect to the login page if the user is not logged in. """
        self.client.logout()
        response = self.client.post(self.path)
        self.assertEqual(response.status_code, 302)

    @httpretty.activate
    def post_to_receipt_page(self, post_data):
        httpretty.register_uri(httpretty.POST, self.path, body=post_data)

        response = self.client.post(self.path, params={'basket_id': 1}, data=post_data)
        self.assertEqual(response.status_code, 200)
        return response

    @ddt.data('ACCEPT', 'REJECT', 'ERROR')
    def test_cybersource_decision(self, decision):
        """
        Ensure that when Cybersource sends a response back to the view, it renders the page title appropriately
        depending on the decision code provided in response data.
        """
        post_data = {'decision': decision, 'reason_code': '200', 'signed_field_names': 'dummy'}
        expected_pattern = r"<title>(\s+)Receipt" if decision == 'ACCEPT' else r"<title>(\s+)Payment Failed"
        response = self.post_to_receipt_page(post_data)
        self.assertRegexpMatches(response.content, expected_pattern)

    def test_hide_nav_header(self):
        """
        Verify that the header navigation links are hidden for the edx.org version
        """
        post_data = {'decision': 'ACCEPT', 'reason_code': '200', 'signed_field_names': 'dummy'}
        response = self.post_to_receipt_page(post_data)

        self.assertNotContains(response, "How it Works")
        self.assertNotContains(response, "Find courses")
        self.assertNotContains(response, "Schools & Partners")
