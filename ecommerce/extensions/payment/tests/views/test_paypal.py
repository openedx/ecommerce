""" Tests of the Payment Views. """
from __future__ import unicode_literals

import ddt
import mock
import responses
from django.test.client import RequestFactory
from django.urls import reverse
from oscar.apps.order.exceptions import UnableToPlaceOrder
from oscar.apps.payment.exceptions import PaymentError
from oscar.core.loading import get_class, get_model
from oscar.test import factories
from testfixtures import LogCapture

from ecommerce.core.constants import ENROLLMENT_CODE_PRODUCT_CLASS_NAME, ENROLLMENT_CODE_SWITCH
from ecommerce.core.models import BusinessClient
from ecommerce.core.tests import toggle_switch
from ecommerce.courses.tests.factories import CourseFactory
from ecommerce.extensions.basket.utils import basket_add_organization_attribute
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.processors.paypal import Paypal
from ecommerce.extensions.payment.tests.mixins import PaymentEventsMixin, PaypalMixin
from ecommerce.extensions.payment.views.paypal import PaypalPaymentExecutionView
from ecommerce.extensions.test.factories import create_basket
from ecommerce.invoice.models import Invoice
from ecommerce.tests.testcases import TestCase

JSON = 'application/json'

Basket = get_model('basket', 'Basket')
Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
Product = get_model('catalogue', 'Product')
Selector = get_class('partner.strategy', 'Selector')
SourceType = get_model('payment', 'SourceType')
Voucher = get_model('voucher', 'Voucher')


post_checkout = get_class('checkout.signals', 'post_checkout')


@ddt.ddt
class PaypalPaymentExecutionViewTests(PaypalMixin, PaymentEventsMixin, TestCase):
    """Test handling of users redirected by PayPal after approving payment."""

    def setUp(self):
        super(PaypalPaymentExecutionViewTests, self).setUp()

        self.basket = create_basket(owner=factories.UserFactory(), site=self.site)
        self.basket.freeze()

        self.processor = Paypal(self.site)
        self.processor_name = self.processor.NAME

        # Dummy request from which an HTTP Host header can be extracted during
        # construction of absolute URLs
        self.request = RequestFactory().post('/')

    @responses.activate
    def _assert_execution_redirect(self, payer_info=None, url_redirect=None):
        """Verify redirection to Otto receipt page after attempted payment execution."""
        self.mock_oauth2_response()

        # Create a payment record the view can use to retrieve a basket
        self.mock_payment_creation_response(self.basket)
        self.processor.get_transaction_parameters(self.basket, request=self.request)

        creation_response = self.mock_payment_creation_response(self.basket, find=True)
        execution_response = self.mock_payment_execution_response(self.basket, payer_info=payer_info)

        response = self.client.get(reverse('paypal:execute'), self.RETURN_DATA)
        self.assertRedirects(
            response,
            url_redirect or get_receipt_page_url(
                order_number=self.basket.order_number,
                site_configuration=self.basket.site.siteconfiguration
            ),
            fetch_redirect_response=False
        )

        return creation_response, execution_response

    def _assert_order_placement_failure(self, error_message):
        """Verify that order placement fails gracefully."""
        logger_name = 'ecommerce.extensions.payment.views.paypal'
        with LogCapture(logger_name) as l:
            __, execution_response = self._assert_execution_redirect()

            # Verify that the payment execution response was recorded despite the error
            self.assert_processor_response_recorded(
                self.processor_name,
                self.PAYMENT_ID,
                execution_response,
                basket=self.basket
            )

            l.check(
                (
                    logger_name,
                    'INFO',
                    'Payment [{payment_id}] approved by payer [{payer_id}]'.format(
                        payment_id=self.PAYMENT_ID,
                        payer_id=self.PAYER_ID
                    )
                ),
                (logger_name, 'ERROR', error_message)
            )

    @responses.activate
    def test_execution_redirect_to_lms(self):
        """
        Verify redirection to LMS receipt page after attempted payment execution if the Otto receipt page is disabled.
        """
        self.mock_oauth2_response()

        # Create a payment record the view can use to retrieve a basket
        self.mock_payment_creation_response(self.basket)
        self.processor.get_transaction_parameters(self.basket, request=self.request)
        self.mock_payment_execution_response(self.basket)

        response = self.client.get(reverse('paypal:execute'), self.RETURN_DATA)
        self.assertRedirects(
            response,
            get_receipt_page_url(
                order_number=self.basket.order_number,
                site_configuration=self.basket.site.siteconfiguration
            ),
            fetch_redirect_response=False
        )

    @responses.activate
    def test_execution_for_bulk_purchase(self):
        """
        Verify redirection to LMS receipt page after attempted payment
        execution if the Otto receipt page is disabled for bulk purchase and
        also that the order is linked to the provided business client..
        """
        toggle_switch(ENROLLMENT_CODE_SWITCH, True)
        self.mock_oauth2_response()

        course = CourseFactory()
        course.create_or_update_seat('verified', True, 50, self.partner, create_enrollment_code=True)
        self.basket = create_basket(owner=factories.UserFactory(), site=self.site)
        enrollment_code = Product.objects.get(product_class__name=ENROLLMENT_CODE_PRODUCT_CLASS_NAME)
        factories.create_stockrecord(enrollment_code, num_in_stock=2, price_excl_tax='10.00')
        self.basket.add_product(enrollment_code, quantity=1)

        # Create a payment record the view can use to retrieve a basket
        self.mock_payment_creation_response(self.basket)
        self.processor.get_transaction_parameters(self.basket, request=self.request)
        self.mock_payment_execution_response(self.basket)
        self.mock_payment_creation_response(self.basket, find=True)

        # Manually add organization attribute on the basket for testing
        self.RETURN_DATA.update({'organization': 'Dummy Business Client'})
        basket_add_organization_attribute(self.basket, self.RETURN_DATA)

        response = self.client.get(reverse('paypal:execute'), self.RETURN_DATA)
        self.assertRedirects(
            response,
            get_receipt_page_url(
                order_number=self.basket.order_number,
                site_configuration=self.basket.site.siteconfiguration
            ),
            fetch_redirect_response=False
        )

        # Now verify that a new business client has been created and current
        # order is now linked with that client through Invoice model.
        order = Order.objects.filter(basket=self.basket).first()
        business_client = BusinessClient.objects.get(name=self.RETURN_DATA['organization'])
        assert Invoice.objects.get(order=order).business_client == business_client

    @ddt.data(
        None,  # falls back to PaypalMixin.PAYER_INFO, a fully-populated payer_info object
        {"shipping_address": None},  # minimal data, which may be sent in some Paypal execution responses
    )
    def test_payment_execution(self, payer_info):
        """Verify that a user who has approved payment is redirected to the configured receipt page."""
        self._assert_execution_redirect(payer_info=payer_info)
        # even if an exception occurs during handling of the payment notification, we still redirect the
        # user to the receipt page.  Therefore in addition to checking that the response had the correct
        # redirection, we also need to check that the order was actually created.
        self.get_order(self.basket)

    def test_payment_error(self):
        """
        Verify that a user who has approved payment is redirected to the configured receipt page when payment
        execution fails.
        """
        with mock.patch.object(PaypalPaymentExecutionView, 'handle_payment',
                               side_effect=PaymentError) as fake_handle_payment:
            logger_name = 'ecommerce.extensions.payment.views.paypal'
            with LogCapture(logger_name) as l:
                creation_response, __ = self._assert_execution_redirect(url_redirect=self.processor.error_url)
                self.assertTrue(fake_handle_payment.called)

                # Verify that the payment creation response was recorded despite the error
                self.assert_processor_response_recorded(
                    self.processor_name,
                    self.PAYMENT_ID,
                    creation_response,
                    basket=self.basket
                )

                l.check(
                    (
                        logger_name,
                        'INFO',
                        'Payment [{payment_id}] approved by payer [{payer_id}]'.format(
                            payment_id=self.PAYMENT_ID,
                            payer_id=self.PAYER_ID
                        )
                    ),
                )

    def test_unanticipated_error_during_payment_handling(self):
        """
        Verify that a user who has approved payment is redirected to the configured receipt page when payment
        execution fails in an unanticipated manner.
        """
        with mock.patch.object(PaypalPaymentExecutionView, 'handle_payment',
                               side_effect=KeyError) as fake_handle_payment:
            logger_name = 'ecommerce.extensions.payment.views.paypal'
            with LogCapture(logger_name) as l:
                creation_response, __ = self._assert_execution_redirect()
                self.assertTrue(fake_handle_payment.called)

                # Verify that the payment creation response was recorded despite the error
                self.assert_processor_response_recorded(
                    self.processor_name,
                    self.PAYMENT_ID,
                    creation_response,
                    basket=self.basket
                )

                l.check(
                    (
                        logger_name,
                        'INFO',
                        'Payment [{payment_id}] approved by payer [{payer_id}]'.format(
                            payment_id=self.PAYMENT_ID,
                            payer_id=self.PAYER_ID
                        )
                    ),
                    (
                        logger_name,
                        'ERROR',
                        'Attempts to handle payment for basket [{basket_id}] failed.'.format(basket_id=self.basket.id)
                    ),
                )

    def test_unable_to_place_order(self):
        """
        Verify that a user who has approved payment is redirected to the configured receipt page when the payment
        is executed but an order cannot be placed.
        """
        with mock.patch.object(PaypalPaymentExecutionView, 'handle_order_placement',
                               side_effect=UnableToPlaceOrder) as fake_handle_order_placement:
            error_message = 'Order Failure: Payment was received, but an order for basket [{basket_id}] ' \
                            'could not be placed because of exception [].'.format(basket_id=self.basket.id)
            self._assert_order_placement_failure(error_message)
            self.assertTrue(fake_handle_order_placement.called)

    def test_unanticipated_error_during_order_placement(self):
        """Verify that unanticipated errors during order placement are handled gracefully."""
        with mock.patch.object(PaypalPaymentExecutionView, 'handle_order_placement',
                               side_effect=KeyError) as fake_handle_order_placement:
            error_message = 'Order Failure: Payment was received, but an order for basket [{basket_id}] ' \
                            'could not be placed because of exception [].'.format(basket_id=self.basket.id)
            self._assert_order_placement_failure(error_message)
            self.assertTrue(fake_handle_order_placement.called)

    @responses.activate
    def test_payment_error_with_duplicate_payment_id(self):
        """
        Verify that we fail gracefully when PayPal sends us the wrong payment ID,
        logging the exception and redirecting the user to an LMS checkout error page.
        """
        logger_name = 'ecommerce.extensions.payment.views.paypal'
        with LogCapture(logger_name) as l:
            self.mock_oauth2_response()

            # Create payment records with different baskets which will have same payment ID
            self.mock_payment_creation_response(self.basket)
            self.processor.get_transaction_parameters(self.basket, request=self.request)

            dummy_basket = create_basket()
            self.mock_payment_creation_response(dummy_basket)
            self.processor.get_transaction_parameters(dummy_basket, request=self.request)

            self._assert_error_page_redirect()
            l.check(
                (
                    logger_name,
                    'INFO',
                    'Payment [{payment_id}] approved by payer [{payer_id}]'.format(
                        payment_id=self.PAYMENT_ID,
                        payer_id=self.PAYER_ID
                    )
                ),
                (
                    logger_name,
                    'WARNING',
                    'Duplicate payment ID [{payment_id}] received from PayPal.'.format(payment_id=self.PAYMENT_ID),
                ),
            )

    @responses.activate
    def test_payment_error_with_no_basket(self):
        """
        Verify that we fail gracefully when any Exception occurred in _get_basket() method,
        logging the exception and redirecting the user to an LMS checkout error page.
        """
        with mock.patch.object(PaymentProcessorResponse.objects, 'get', side_effect=Exception):
            logger_name = 'ecommerce.extensions.payment.views.paypal'
            with LogCapture(logger_name) as l:
                self.mock_oauth2_response()
                self.mock_payment_creation_response(self.basket)
                self.processor.get_transaction_parameters(self.basket, request=self.request)
                self._assert_error_page_redirect()

                l.check(
                    (
                        logger_name,
                        'INFO',
                        'Payment [{payment_id}] approved by payer [{payer_id}]'.format(
                            payment_id=self.PAYMENT_ID,
                            payer_id=self.PAYER_ID
                        )
                    ),
                    (
                        logger_name,
                        'ERROR',
                        'Unexpected error during basket retrieval while executing PayPal payment.'
                    ),
                )

    def _assert_error_page_redirect(self):
        """Verify redirection to the configured checkout error page after attempted failed payment execution."""
        response = self.client.get(reverse('paypal:execute'), self.RETURN_DATA)

        self.assertRedirects(
            response,
            self.processor.error_url,
            fetch_redirect_response=False
        )


@mock.patch('ecommerce.extensions.payment.views.paypal.call_command')
class PaypalProfileAdminViewTests(TestCase):
    path = reverse('paypal:profiles')

    def get_response(self, is_superuser, expected_status, data=None):
        user = self.create_user(is_superuser=is_superuser)
        self.client.login(username=user.username, password=self.password)
        response = self.client.get(self.path, data=data or {})
        self.assertEqual(response.status_code, expected_status)
        return response

    def test_superuser_required(self, mock_call_command):
        """ Verify the view is only accessible to superusers. """
        response = self.client.get(self.path)
        self.assertFalse(mock_call_command.called)
        self.assertEqual(response.status_code, 404)

        self.get_response(False, 404)
        self.assertFalse(mock_call_command.called)

    def test_valid_action_required(self, mock_call_command):
        self.get_response(True, 400)
        self.assertFalse(mock_call_command.called)

        self.get_response(True, 400, {"action": "invalid"})
        self.assertFalse(mock_call_command.called)

        self.get_response(True, 200, {"action": "list"})
        self.assertTrue(mock_call_command.called)

    def test_command_exception(self, mock_call_command):
        mock_call_command.side_effect = Exception("oof")
        self.get_response(True, 500, {"action": "list"})
        self.assertTrue(mock_call_command.called)
