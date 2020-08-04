

from decimal import Decimal
from urllib import parse

import ddt
import httpretty
from django.conf import settings
from django.urls import reverse
from mock import patch
from oscar.core.loading import get_model
from oscar.test import factories

from ecommerce.core.url_utils import get_lms_courseware_url, get_lms_program_dashboard_url
from ecommerce.coupons.tests.mixins import DiscoveryMockMixin
from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.basket.tests.test_utils import TEST_BUNDLE_ID
from ecommerce.extensions.checkout.exceptions import BasketNotFreeError
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.checkout.views import ReceiptResponseView
from ecommerce.extensions.refund.tests.mixins import RefundTestMixin
from ecommerce.tests.mixins import LmsApiMockMixin
from ecommerce.tests.testcases import TestCase

Basket = get_model('basket', 'Basket')
BasketAttribute = get_model('basket', 'BasketAttribute')
BasketAttributeType = get_model('basket', 'BasketAttributeType')
Order = get_model('order', 'Order')


class FreeCheckoutViewTests(EnterpriseServiceMockMixin, TestCase):
    """ FreeCheckoutView view tests. """
    path = reverse('checkout:free-checkout')

    def setUp(self):
        super(FreeCheckoutViewTests, self).setUp()
        self.user = self.create_user()
        self.bundle_attribute_value = TEST_BUNDLE_ID
        self.client.login(username=self.user.username, password=self.password)

    def prepare_basket(self, price, bundle=False):
        """ Helper function that creates a basket and adds a product with set price to it. """
        basket = factories.BasketFactory(owner=self.user, site=self.site)
        self.course_run.create_or_update_seat('verified', True, Decimal(price))
        basket.add_product(self.course_run.seat_products[0])
        self.assertEqual(basket.lines.count(), 1)
        self.assertEqual(basket.total_incl_tax, Decimal(price))

        if bundle:
            BasketAttribute.objects.update_or_create(
                basket=basket,
                attribute_type=BasketAttributeType.objects.get(name='bundle_identifier'),
                value_text=self.bundle_attribute_value
            )

    def test_empty_basket(self):
        """ Verify redirect to basket summary in case of empty basket. """
        response = self.client.get(self.path)
        expected_url = reverse('basket:summary')
        self.assertRedirects(response, expected_url)

    def test_non_free_basket(self):
        """ Verify an exception is raised when the URL is being accessed to with a non-free basket. """
        self.prepare_basket(10)

        with self.assertRaises(BasketNotFreeError):
            self.client.get(self.path)

    @httpretty.activate
    def test_enterprise_offer_program_redirect(self):
        """ Verify redirect to the program dashboard page. """
        self.prepare_basket(10, bundle=True)
        self.prepare_enterprise_offer()
        self.assertEqual(Order.objects.count(), 0)
        response = self.client.get(self.path)
        self.assertEqual(Order.objects.count(), 1)

        expected_url = get_lms_program_dashboard_url(self.bundle_attribute_value)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @httpretty.activate
    def test_enterprise_offer_course_redirect(self):
        """ Verify redirect to the courseware info page. """
        self.prepare_basket(10)
        self.prepare_enterprise_offer()
        self.assertEqual(Order.objects.count(), 0)
        response = self.client.get(self.path)
        self.assertEqual(Order.objects.count(), 1)

        expected_url = get_lms_courseware_url(self.course_run.id)
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    @httpretty.activate
    def test_successful_redirect(self):
        """ Verify redirect to the receipt page. """
        self.prepare_basket(0)
        self.assertEqual(Order.objects.count(), 0)
        response = self.client.get(self.path)
        self.assertEqual(Order.objects.count(), 1)

        order = Order.objects.first()
        expected_url = get_receipt_page_url(
            order_number=order.number,
            site_configuration=order.site.siteconfiguration,
            disable_back_button=True,
        )
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
class ReceiptResponseViewTests(DiscoveryMockMixin, LmsApiMockMixin, RefundTestMixin, TestCase):
    """
    Tests for the receipt view.
    """

    path = reverse('checkout:receipt')

    def setUp(self):
        super(ReceiptResponseViewTests, self).setUp()
        self.user = self.create_user()
        self.client.login(username=self.user.username, password=self.password)
        # Note: actual response is far more rich. Just including the bits relevant to us
        self.enterprise_learner_data_no_portal = {
            'results': [{
                'enterprise_customer': {
                    'name': 'Test Company',
                    'slug': 'test-company',
                    'enable_learner_portal': False,
                }
            }]
        }
        self.enterprise_learner_data_with_portal = {
            'results': [{
                'enterprise_customer': {
                    'name': 'Test Company',
                    'slug': 'test-company',
                    'enable_learner_portal': True,
                }
            }]
        }
        self.non_enterprise_learner_data = {}

    def _get_receipt_response(self, order_number):
        """
        Helper function for getting the receipt page response for an order.

        Arguments:
            order_number (str): Number of Order for which the Receipt Page should be opened.

        Returns:
            response (Response): Response object that's returned by a ReceiptResponseView
        """
        url = '{path}?order_number={order_number}'.format(path=self.path, order_number=order_number)
        return self.client.get(url)

    def _visit_receipt_page_with_another_user(self, order, user):
        """
        Helper function for logging in with another user and going to the Receipt Page.

        Arguments:
            order (Order): Order for which the Receipt Page should be opened.
            user (User): User that's logging in.

        Returns:
            response (Response): Response object that's returned by a ReceiptResponseView
        """
        self.client.logout()
        self.client.login(username=user.username, password=self.password)
        return self._get_receipt_response(order.number)

    def _create_order_for_receipt(self, user, credit=False, entitlement=False, id_verification_required=False):
        """
        Helper function for creating an order and mocking verification status API response.

        Arguments:
            user (User): User that's trying to visit the Receipt page.
            credit (bool): Indicates whether or not the product is a Credit Course Seat.

        Returns:
            order (Order): Order for which the Receipt is requested.
        """
        self.mock_verification_status_api(
            self.site,
            user,
            status=200,
            is_verified=False
        )
        return self.create_order(
            credit=credit,
            entitlement=entitlement,
            id_verification_required=id_verification_required
        )

    def test_login_required_get_request(self):
        """ The view should redirect to the login page if the user is not logged in. """
        self.client.logout()
        response = self.client.get(self.path)
        expected_url = '{path}?next={next}'.format(path=reverse(settings.LOGIN_URL),
                                                   next=parse.quote(self.path))
        self.assertRedirects(response, expected_url, target_status_code=302)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    def test_get_receipt_for_nonexisting_order(self, mock_learner_data):
        """ The view should return 404 status if the Order is not found. """
        mock_learner_data.return_value = self.non_enterprise_learner_data
        order_number = 'ABC123'
        response = self._get_receipt_response(order_number)
        self.assertEqual(response.status_code, 404)

    def test_get_payment_method_no_source(self):
        """ Payment method should be None when an Order has no Payment source. """
        order = self.create_order()
        payment_method = ReceiptResponseView().get_payment_method(order)
        self.assertEqual(payment_method, None)

    def test_get_payment_method_source_type(self):
        """
        Source Type name should be displayed as the Payment method
        when the credit card wasn't used to purchase a product.
        """
        order = self.create_order()
        source = factories.SourceFactory(order=order)
        payment_method = ReceiptResponseView().get_payment_method(order)
        self.assertEqual(payment_method, source.source_type.name)

    def test_get_payment_method_credit_card_purchase(self):
        """
        Credit card type and Source label should be displayed as the Payment method
        when a Credit card was used to purchase a product.
        """
        order = self.create_order()
        source = factories.SourceFactory(order=order, card_type='Dummy Card', label='Test')
        payment_method = ReceiptResponseView().get_payment_method(order)
        self.assertEqual(payment_method, '{} {}'.format(source.card_type, source.label))

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_get_receipt_for_existing_order(self, mock_learner_data):
        """ Order owner should be able to see the Receipt Page."""
        mock_learner_data.return_value = self.non_enterprise_learner_data
        order = self._create_order_for_receipt(self.user)
        response = self._get_receipt_response(order.number)
        context_data = {
            'payment_method': None,
            'display_credit_messaging': False,
            'verification_url': self.site.siteconfiguration.build_lms_url('verify_student/reverify'),
        }

        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(context_data, response.context_data)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_get_receipt_for_existing_entitlement_order(self, mock_learner_data):
        """ Order owner should be able to see the Receipt Page."""

        mock_learner_data.return_value = self.non_enterprise_learner_data
        order = self._create_order_for_receipt(self.user, entitlement=True, id_verification_required=True)
        response = self._get_receipt_response(order.number)
        context_data = {
            'payment_method': None,
            'display_credit_messaging': False,
            'verification_url': self.site.siteconfiguration.build_lms_url('verify_student/reverify'),
        }

        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(context_data, response.context_data)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_get_receipt_for_entitlement_order_no_id_required(self, mock_learner_data):
        """ Order owner should be able to see the Receipt Page with no ID verification in context."""

        mock_learner_data.return_value = self.non_enterprise_learner_data
        order = self._create_order_for_receipt(self.user, entitlement=True, id_verification_required=False)
        response = self._get_receipt_response(order.number)
        context_data = {
            'payment_method': None,
            'display_credit_messaging': False,
        }

        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(context_data, response.context_data)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_get_receipt_for_existing_order_as_staff_user(self, mock_learner_data):
        """ Staff users can preview Receipts for all Orders."""
        mock_learner_data.return_value = self.non_enterprise_learner_data
        staff_user = self.create_user(is_staff=True)
        order = self._create_order_for_receipt(staff_user)
        response = self._visit_receipt_page_with_another_user(order, staff_user)
        context_data = {
            'payment_method': None,
            'display_credit_messaging': False,
        }

        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(context_data, response.context_data)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_get_receipt_for_existing_order_user_not_owner(self, mock_learner_data):
        """ Users that don't own the Order shouldn't be able to see the Receipt. """
        mock_learner_data.return_value = self.non_enterprise_learner_data
        other_user = self.create_user()
        order = self._create_order_for_receipt(other_user)
        response = self._visit_receipt_page_with_another_user(order, other_user)
        context_data = {'order_history_url': self.site.siteconfiguration.build_lms_url('account/settings')}

        self.assertEqual(response.status_code, 404)
        self.assertDictContainsSubset(context_data, response.context_data)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_order_data_for_credit_seat(self, mock_learner_data):
        """ Ensure that the context is updated with Order data. """
        mock_learner_data.return_value = self.non_enterprise_learner_data
        order = self.create_order(credit=True)
        self.mock_verification_status_api(
            self.site,
            self.user,
            status=200,
            is_verified=True
        )
        seat = order.lines.first().product
        body = {'display_name': 'Hogwarts'}

        response = self._get_receipt_response(order.number)

        body['course_key'] = seat.attr.course_key
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context_data['display_credit_messaging'])

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_order_value_unlocalized_for_tracking(self, mock_learner_data):
        mock_learner_data.return_value = self.non_enterprise_learner_data
        order = self._create_order_for_receipt(self.user)
        self.client.cookies.load({settings.LANGUAGE_COOKIE_NAME: 'fr'})
        response = self._get_receipt_response(order.number)

        self.assertEqual(response.status_code, 200)
        order_value_string = 'data-total-amount="{}"'.format(order.total_incl_tax)
        self.assertContains(response, order_value_string)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_dashboard_link_for_course_purchase(self, mock_learner_data):
        """
        The dashboard link at the bottom of the receipt for a course purchase
        should point to the user dashboard.
        """
        mock_learner_data.return_value = self.non_enterprise_learner_data
        order = self._create_order_for_receipt(self.user)
        response = self._get_receipt_response(order.number)
        context_data = {
            'order_dashboard_url': self.site.siteconfiguration.build_lms_url('dashboard')
        }

        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(context_data, response.context_data)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_dashboard_link_for_bundle_purchase(self, mock_learner_data):
        """
        The dashboard link at the bottom of the receipt for a bundle purchase
        should point to the program dashboard.
        """
        mock_learner_data.return_value = self.non_enterprise_learner_data
        order = self._create_order_for_receipt(self.user)
        bundle_id = TEST_BUNDLE_ID
        BasketAttribute.objects.update_or_create(
            basket=order.basket,
            attribute_type=BasketAttributeType.objects.get(name='bundle_identifier'),
            value_text=bundle_id
        )

        response = self._get_receipt_response(order.number)
        context_data = {
            'order_dashboard_url': self.site.siteconfiguration.build_lms_url(
                'dashboard/programs/{}'.format(bundle_id)
            )
        }

        self.assertEqual(response.status_code, 200)
        self.assertDictContainsSubset(context_data, response.context_data)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_order_without_basket(self, mock_learner_data):
        mock_learner_data.return_value = self.non_enterprise_learner_data
        order = self.create_order()
        Basket.objects.filter(id=order.basket.id).delete()
        response = self._get_receipt_response(order.number)
        self.assertEqual(response.status_code, 200)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_enterprise_learner_dashboard_link_in_messages(self, mock_learner_data):
        """
        The receipt page should include a message with a link to the enterprise
        learner portal for a learner if response from enterprise shows the portal
        is configured.
        """
        mock_learner_data.return_value = self.enterprise_learner_data_with_portal
        order = self._create_order_for_receipt(self.user)
        BasketAttribute.objects.update_or_create(
            basket=order.basket,
            attribute_type=BasketAttributeType.objects.get(name='bundle_identifier'),
            value_text=TEST_BUNDLE_ID
        )

        response = self._get_receipt_response(order.number)
        response_messages = list(response.context['messages'])

        expected_message = (
            'Your company, Test Company, has a dedicated page where you can see all of '
            'your sponsored courses. Go to <a href="http://{}/test-company">'
            'your learner portal</a>.'
        ).format(settings.ENTERPRISE_LEARNER_PORTAL_HOSTNAME)
        actual_message = str(response_messages[0])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response_messages), 1)
        self.assertEqual(expected_message, actual_message)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    @ddt.data(
        ({'results': []}, None),
        (None, [KeyError])
    )
    @ddt.unpack
    def test_enterprise_not_enabled_for_learner_dashboard_link_in_messages(self, learner_data,
                                                                           exception, mock_learner_data):
        """
        The receipt page should not include a message with a link to the enterprise
        learner portal for a learner if response from enterprise is empty results or error.
        """
        mock_learner_data.side_effect = exception
        mock_learner_data.return_value = learner_data
        order = self._create_order_for_receipt(self.user)
        BasketAttribute.objects.update_or_create(
            basket=order.basket,
            attribute_type=BasketAttributeType.objects.get(name='bundle_identifier'),
            value_text='test_bundle'
        )

        response = self._get_receipt_response(order.number)
        response_messages = list(response.context['messages'])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response_messages), 0)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_no_enterprise_learner_dashboard_link_in_messages(self, mock_learner_data):
        """
        The receipt page should NOT include a message with a link to the enterprise
        learner portal for a learner if response from enterprise shows the portal
        is not configured.
        """
        mock_learner_data.return_value = self.enterprise_learner_data_no_portal
        order = self._create_order_for_receipt(self.user)
        BasketAttribute.objects.update_or_create(
            basket=order.basket,
            attribute_type=BasketAttributeType.objects.get(name='bundle_identifier'),
            value_text=TEST_BUNDLE_ID
        )

        response = self._get_receipt_response(order.number)
        response_messages = list(response.context['messages'])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response_messages), 0)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_order_dashboard_url_points_to_enterprise_learner_portal(self, mock_learner_data):
        """
        The "Go to dashboard" link at the bottom of the receipt page should
        point to the enterprise learner portal if the response from enterprise
        shows the portal is configured
        """
        mock_learner_data.return_value = self.enterprise_learner_data_with_portal
        order = self._create_order_for_receipt(self.user)
        BasketAttribute.objects.update_or_create(
            basket=order.basket,
            attribute_type=BasketAttributeType.objects.get(name='bundle_identifier'),
            value_text='test_bundle'
        )
        response = self._get_receipt_response(order.number)
        expected_dashboard_url = (
            "http://" +
            settings.ENTERPRISE_LEARNER_PORTAL_HOSTNAME +
            "/test-company"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data['order_dashboard_url'], expected_dashboard_url)

    @patch('ecommerce.extensions.checkout.views.fetch_enterprise_learner_data')
    @httpretty.activate
    def test_go_to_dashboard_points_to_lms_dashboard(self, mock_learner_data):
        """
        The "Go to dashboard" link at the bottom of the receipt page should
        point to the lms dashboard if the response from enterprise
        shows the portal is not configured
        """
        mock_learner_data.return_value = self.enterprise_learner_data_no_portal
        order = self._create_order_for_receipt(self.user)
        BasketAttribute.objects.update_or_create(
            basket=order.basket,
            attribute_type=BasketAttributeType.objects.get(name='bundle_identifier'),
            value_text='test_bundle'
        )
        response = self._get_receipt_response(order.number)
        expected_dashboard_url = self.site.siteconfiguration.build_lms_url('dashboard/programs/test_bundle')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data['order_dashboard_url'], expected_dashboard_url)
