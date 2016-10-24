# -*- coding: utf-8 -*-
"""Unit tests of Paypal payment processor implementation."""
from __future__ import unicode_literals

import json
import logging
from urlparse import urljoin

import ddt
import mock
import paypalrestsdk
from django.conf import settings
from django.core.urlresolvers import reverse
from django.test import RequestFactory
from oscar.apps.payment.exceptions import GatewayError
from oscar.core.loading import get_model
from paypalrestsdk.resource import Resource  # pylint:disable=ungrouped-imports
from testfixtures import LogCapture

from ecommerce.core.tests import toggle_switch
from ecommerce.core.tests.patched_httpretty import httpretty
from ecommerce.extensions.checkout.utils import get_receipt_page_url
from ecommerce.extensions.payment.models import PaypalWebProfile
from ecommerce.extensions.payment.processors.paypal import Paypal
from ecommerce.extensions.payment.tests.mixins import PaypalMixin
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.tests.testcases import TestCase

log = logging.getLogger(__name__)

PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
SourceType = get_model('payment', 'SourceType')


@ddt.ddt
class PaypalTests(PaypalMixin, PaymentProcessorTestCaseMixin, TestCase):
    """Tests for the PayPal payment processor."""
    ERROR = {'debug_id': 'foo'}

    processor_class = Paypal
    processor_name = 'paypal'

    @classmethod
    def setUpClass(cls):
        """
        Class set up - setting static up paypal sdk configuration to be used in test methods
        """
        super(PaypalTests, cls).setUpClass()  # required to pass CI build

        # The test uses objects from paypalrestsdk classes extensively, and those classes require
        # paypal configuration to be passed either globally (via paypalrestsdk.configure) or as a parameter
        # to object constructor (api=..., as in Paypal payment processor class)
        paypal_configuration = settings.PAYMENT_PROCESSOR_CONFIG['edx']['paypal']
        paypalrestsdk.configure({
            'mode': paypal_configuration['mode'],
            'client_id': paypal_configuration['client_id'],
            'client_secret': paypal_configuration['client_secret']
        })

    def setUp(self):
        """
        setUp method
        """
        super(PaypalTests, self).setUp()

        # Dummy request from which an HTTP Host header can be extracted during
        # construction of absolute URLs
        self.request = RequestFactory().post('/')
        self.processor_response_log = (
            u"Failed to execute PayPal payment on attempt [{attempt_count}]. "
            u"PayPal's response was recorded in entry [{entry_id}]."
        )

    def _assert_transaction_parameters(self):
        """DRY helper for verifying transaction parameters."""
        expected = {
            'payment_page_url': self.APPROVAL_URL,
        }
        actual = self.processor.get_transaction_parameters(self.basket, request=self.request)
        self.assertEqual(actual, expected)

    def _get_receipt_url(self):
        """DRY helper for getting receipt page URL."""
        return get_receipt_page_url(site_configuration=self.site.siteconfiguration)

    def _assert_transaction_parameters_retry(self, response_success, failure_log_message):
        self.processor.retry_attempts = 2
        logger_name = 'ecommerce.extensions.payment.processors.paypal'

        with LogCapture(logger_name) as paypal_logger:
            self._assert_transaction_parameters()
            self.assert_processor_response_recorded(
                self.processor.NAME,
                self.PAYMENT_ID,
                response_success,
                basket=self.basket
            )

            last_request_body = json.loads(httpretty.last_request().body)
            expected = urljoin(self.site.siteconfiguration.build_ecommerce_url(), reverse('paypal_execute'))
            self.assertEqual(last_request_body['redirect_urls']['return_url'], expected)
            paypal_logger.check(
                (
                    logger_name,
                    'WARNING',
                    failure_log_message,
                ),
                (
                    logger_name,
                    'INFO',
                    'Successfully created PayPal payment [{}] for basket [{}].'.format(self.PAYMENT_ID, self.basket.id)
                )
            )

    @httpretty.activate
    def test_get_transaction_parameters(self):
        """Verify the processor returns the appropriate parameters required to complete a transaction."""
        self.mock_oauth2_response()
        response = self.mock_payment_creation_response(self.basket)

        self._assert_transaction_parameters()
        self.assert_processor_response_recorded(self.processor.NAME, self.PAYMENT_ID, response, basket=self.basket)

        last_request_body = json.loads(httpretty.last_request().body)
        expected = urljoin(self.site.siteconfiguration.build_ecommerce_url(), reverse('paypal_execute'))
        self.assertEqual(last_request_body['redirect_urls']['return_url'], expected)

    @httpretty.activate
    def test_get_transaction_parameters_with_retry(self):
        """Verify the processor returns the appropriate parameters required to complete a transaction after a retry"""
        toggle_switch('PAYPAL_RETRY_ATTEMPTS', True)
        self.mock_oauth2_response()
        response_error = self.get_payment_creation_error_response_mock()
        response_success = self.get_payment_creation_response_mock(self.basket)
        self.mock_api_responses(
            '/v1/payments/payment',
            [
                {'body': response_error, 'status': 200},
                {'body': response_success, 'status': 200}
            ]
        )
        self._assert_transaction_parameters_retry(
            response_success,
            'Creating PayPal payment for basket [{}] was unsuccessful. Will retry.'.format(self.basket.id)
        )

    @httpretty.activate
    def test_get_transaction_parameters_server_error_with_retry(self):
        """
        Verify the processor returns the appropriate parameters required
        to complete a transaction after a retry with server error
        """
        toggle_switch('PAYPAL_RETRY_ATTEMPTS', True)
        self.mock_oauth2_response()
        response_error = self.get_payment_creation_error_response_mock()
        response_success = self.get_payment_creation_response_mock(self.basket)
        self.mock_api_responses(
            '/v1/payments/payment',
            [
                {'body': response_error, 'status': 500},
                {'body': response_success, 'status': 200}
            ]
        )
        self._assert_transaction_parameters_retry(
            response_success,
            'Creating PayPal payment for basket [{}] resulted in an exception. Will retry.'.format(self.basket.id)
        )

    def test_switch_enabled_otto_url(self):
        """
        Ensures that when the otto_receipt_page waffle switch is enabled, the processor uses the new receipt page.
        """
        self.toggle_ecommerce_receipt_page(True)
        assert self._get_receipt_url() == self.site.siteconfiguration.build_ecommerce_url(settings.RECEIPT_PAGE_PATH)

    def test_switch_disabled_lms_url(self):
        """
        Ensures that when the otto_receipt_page waffle switch is disabled, the processor uses the LMS receipt page.
        """
        self.site.siteconfiguration.enable_otto_receipt_page = False
        assert self._get_receipt_url() == self.site.siteconfiguration.build_lms_url('/commerce/checkout/receipt')

    @httpretty.activate
    @mock.patch('ecommerce.extensions.payment.processors.paypal.paypalrestsdk.Payment')
    @ddt.data(None, Paypal.DEFAULT_PROFILE_NAME, "some-other-name")
    def test_web_profiles(self, enabled_profile_name, mock_payment):
        """
        Verify that the payment creation payload references a web profile when one is enabled with the expected name.
        """
        mock_payment_instance = mock.Mock()
        mock_payment_instance.to_dict.return_value = {}
        mock_payment_instance.links = [mock.Mock(rel='approval_url', href='dummy')]
        mock_payment.return_value = mock_payment_instance
        if enabled_profile_name is not None:
            PaypalWebProfile.objects.create(name=enabled_profile_name, id="test-profile-id")

        self.processor.get_transaction_parameters(self.basket, request=self.request)
        payment_creation_payload = mock_payment.call_args[0][0]
        if enabled_profile_name == Paypal.DEFAULT_PROFILE_NAME:
            self.assertEqual(payment_creation_payload['experience_profile_id'], "test-profile-id")
        else:
            self.assertNotIn('experience_profile_id', payment_creation_payload)

    @httpretty.activate
    @mock.patch.object(Paypal, '_get_error', mock.Mock(return_value=ERROR))
    def test_unexpected_payment_creation_state(self):
        """Verify that failure to create a payment results in a GatewayError."""
        self.mock_oauth2_response()
        self.mock_payment_creation_response(self.basket)

        with mock.patch.object(paypalrestsdk.Payment, 'success', return_value=False):
            self.assertRaises(
                GatewayError,
                self.processor.get_transaction_parameters,
                self.basket,
                request=self.request
            )
            self.assert_processor_response_recorded(
                self.processor.NAME,
                self.ERROR['debug_id'],
                self.ERROR,
                basket=self.basket
            )

    @httpretty.activate
    def test_payment_creation_exception_state(self):
        """Verify that an exception is thrown while create a payment results in paypal exception."""
        self.mock_oauth2_response()
        response_error = self.get_payment_creation_error_response_mock()
        self.mock_api_responses(
            '/v1/payments/payment',
            [{'body': response_error, 'status': 500}]
        )
        logger_name = 'ecommerce.extensions.payment.processors.paypal'

        with LogCapture(logger_name) as paypal_logger:
            self.assertRaises(
                paypalrestsdk.exceptions.ServerError,
                self.processor.get_transaction_parameters,
                self.basket,
                request=self.request
            )
            paypal_logger.check(
                (
                    logger_name,
                    'ERROR',
                    'After {} retries, creating PayPal payment for basket [{}] still experienced exception.'
                    .format(self.processor.retry_attempts + 1, self.basket.id)
                )
            )

    @httpretty.activate
    def test_approval_url_missing(self):
        """Verify that a missing approval URL results in a GatewayError."""
        self.mock_oauth2_response()
        response = self.mock_payment_creation_response(self.basket, approval_url=None)

        self.assertRaises(GatewayError, self.processor.get_transaction_parameters, self.basket, request=self.request)
        self.assert_processor_response_recorded(self.processor.NAME, self.PAYMENT_ID, response, basket=self.basket)

    @httpretty.activate
    def test_handle_processor_response(self):
        """Verify that the processor creates the appropriate PaymentEvent and Source objects."""
        for payer_info in (PaypalMixin.PAYER_INFO, {"shipping_address": None}):
            httpretty.reset()
            log.info("Testing payer_info with email set to: %s", payer_info.get("email"))
            self.mock_oauth2_response()
            self.mock_payment_creation_response(self.basket, find=True)
            self.mock_payment_execution_response(self.basket, payer_info=payer_info)

            handled_response = self.processor.handle_processor_response(self.RETURN_DATA, basket=self.basket)
            self.assertEqual(handled_response.currency, self.basket.currency)
            self.assertEqual(handled_response.total, self.basket.total_incl_tax)
            self.assertEqual(handled_response.transaction_id, self.PAYMENT_ID)
            self.assertEqual(
                handled_response.card_number,
                'PayPal ({})'.format(payer_info['email']) if 'email' in payer_info else 'PayPal Account')
            self.assertIsNone(handled_response.card_type)

    @httpretty.activate
    @mock.patch.object(Paypal, '_get_error', mock.Mock(return_value=ERROR))
    def test_unexpected_payment_execution_state(self):
        """Verify that failure to execute a payment results in a GatewayError."""
        self.mock_oauth2_response()
        self.mock_payment_creation_response(self.basket, find=True)
        self.mock_payment_execution_response(self.basket)

        with mock.patch.object(paypalrestsdk.Payment, 'success', return_value=False):
            logger_name = 'ecommerce.extensions.payment.processors.paypal'
            with LogCapture(logger_name) as paypal_logger:
                self.assertRaises(GatewayError, self.processor.handle_processor_response, self.RETURN_DATA, self.basket)
                payment_processor_response = self.assert_processor_response_recorded(
                    self.processor.NAME,
                    self.ERROR['debug_id'],
                    self.ERROR,
                    basket=self.basket
                )

                paypal_logger.check(
                    (
                        logger_name, 'WARNING', self.processor_response_log.format(
                            attempt_count=1,
                            entry_id=payment_processor_response
                        )
                    ),
                    (
                        logger_name, 'ERROR',
                        u"Failed to execute PayPal payment [{payment_id}]. "
                        u"PayPal's response was recorded in entry [{entry_id}].".format(
                            payment_id=self.PAYMENT_ID,
                            entry_id=payment_processor_response
                        )
                    ),
                )

    @httpretty.activate
    @mock.patch.object(Paypal, '_get_error', mock.Mock(return_value=ERROR))
    def test_unexpected_payment_execution_with_retry_attempt(self):
        """Verify that, when the switch is active, failure to execute a payment
        results in one, or more, retry attempts. If all attempts fail, verify a
        GatewayError is raised.
        """
        toggle_switch('PAYPAL_RETRY_ATTEMPTS', True)
        self.processor.retry_attempts = 1
        self.mock_oauth2_response()
        self.mock_payment_creation_response(self.basket, find=True)
        self.mock_payment_execution_response(self.basket)

        with mock.patch.object(paypalrestsdk.Payment, 'success', return_value=False):
            logger_name = 'ecommerce.extensions.payment.processors.paypal'
            with LogCapture(logger_name) as paypal_logger:
                self.assertRaises(GatewayError, self.processor.handle_processor_response, self.RETURN_DATA, self.basket)

                # Each failure response is saved into db.
                payment_processor_responses = self.assert_processor_multiple_response_recorded()

                paypal_logger.check(
                    (
                        logger_name, 'WARNING', self.processor_response_log.format(
                            attempt_count=1,
                            entry_id=payment_processor_responses[0]
                        )
                    ),
                    (
                        logger_name, 'WARNING', self.processor_response_log.format(
                            attempt_count=2,
                            entry_id=payment_processor_responses[1]
                        )
                    ),
                    (
                        logger_name, 'ERROR',
                        u"Failed to execute PayPal payment [{payment_id}]. "
                        u"PayPal's response was recorded in entry [{entry_id}].".format(
                            payment_id=self.PAYMENT_ID,
                            entry_id=payment_processor_responses[1]
                        )
                    ),
                )

    def test_issue_credit(self):
        """
        Tests issuing credit with Paypal processor
        """
        refund = self.create_refund(self.processor_name)
        order = refund.order
        basket = order.basket
        amount = refund.total_credit_excl_tax
        currency = refund.currency
        source = order.sources.first()

        transaction_id = 'PAY-REFUND-1'
        paypal_refund = paypalrestsdk.Refund({'id': transaction_id})

        payment = paypalrestsdk.Payment({
            'transactions': [
                Resource({'related_resources': [Resource({'sale': paypalrestsdk.Sale({'id': 'PAY-SALE-1'})})]})
            ]
        })
        with mock.patch.object(paypalrestsdk.Payment, 'find', return_value=payment):
            with mock.patch.object(paypalrestsdk.Sale, 'refund', return_value=paypal_refund):
                actual_transaction_id = self.processor.issue_credit(order, source.reference, amount, currency)
                self.assertEqual(actual_transaction_id, transaction_id)

        # Verify PaymentProcessorResponse created
        self.assert_processor_response_recorded(self.processor.NAME, transaction_id, {'id': transaction_id}, basket)

    def test_issue_credit_error(self):
        """
        Tests issue credit fails in case of erroneous response or exceptions
        """
        refund = self.create_refund(self.processor_name)
        order = refund.order
        basket = order.basket
        amount = refund.total_credit_excl_tax
        currency = refund.currency
        source = order.sources.first()

        transaction_id = 'PAY-REFUND-FAIL-1'
        expected_response = {'debug_id': transaction_id}
        paypal_refund = paypalrestsdk.Refund({'error': expected_response})

        payment = paypalrestsdk.Payment({
            'transactions': [
                Resource({'related_resources': [Resource({'sale': paypalrestsdk.Sale({'id': 'PAY-SALE-1'})})]})
            ]
        })

        # Test general exception
        with mock.patch.object(paypalrestsdk.Payment, 'find', return_value=payment):
            with mock.patch.object(paypalrestsdk.Sale, 'refund', side_effect=ValueError):
                self.assertRaises(GatewayError, self.processor.issue_credit, order, source.reference, amount, currency)
                self.assertEqual(source.amount_refunded, 0)

        # Test error response
        with mock.patch.object(paypalrestsdk.Payment, 'find', return_value=payment):
            with mock.patch.object(paypalrestsdk.Sale, 'refund', return_value=paypal_refund):
                self.assertRaises(GatewayError, self.processor.issue_credit, order, source.reference, amount, currency)

        # Verify PaymentProcessorResponse created
        self.assert_processor_response_recorded(self.processor.NAME, transaction_id, expected_response, basket)

    def assert_processor_multiple_response_recorded(self):
        """ Ensures a multiple PaymentProcessorResponse can store in db for the
        corresponding processor and response.
        """
        payment_processor_responses = PaymentProcessorResponse.objects.filter(
            processor_name=self.processor_name,
            transaction_id=self.ERROR['debug_id']
        )
        ids = []
        for payment_response in payment_processor_responses:
            self.assertEqual(payment_response.response, self.ERROR)
            self.assertEqual(payment_response.basket, self.basket)
            ids.append(payment_response.id)

        return ids
