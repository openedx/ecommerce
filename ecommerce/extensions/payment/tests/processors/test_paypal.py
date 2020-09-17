# -*- coding: utf-8 -*-
"""Unit tests of Paypal payment processor implementation."""


import json
import logging
from urllib.parse import urljoin

import ddt
import mock
import paypalrestsdk
import responses
from django.conf import settings
from django.test import RequestFactory
from django.urls import reverse
from django.utils import translation
from factory.fuzzy import FuzzyInteger
from oscar.apps.payment.exceptions import GatewayError
from oscar.core.loading import get_model
from paypalrestsdk.resource import Resource  # pylint:disable=ungrouped-imports
from testfixtures import LogCapture

from ecommerce.core.tests import toggle_switch
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

    def _assert_transaction_parameters_retry(self, api_responses, response_success, failure_log_message):
        self.processor.retry_attempts = 2
        logger_name = 'ecommerce.extensions.payment.processors.paypal'
        toggle_switch('PAYPAL_RETRY_ATTEMPTS', True)
        url = self._create_api_url('/v1/payments/payment')

        with responses.RequestsMock(assert_all_requests_are_fired=True) as rsps:
            self.mock_oauth2_response(rsps=rsps)

            for response in api_responses:
                rsps.add(responses.POST, url, status=response['status'], json=response['body'])

            with LogCapture(logger_name) as paypal_logger:
                self._assert_transaction_parameters()
                self.assert_processor_response_recorded(
                    self.processor.NAME,
                    self.PAYMENT_ID,
                    response_success,
                    basket=self.basket
                )

                last_request_body = json.loads(rsps.calls[-1].request.body)
                expected = urljoin(self.site.siteconfiguration.build_ecommerce_url(), reverse('paypal:execute'))
                self.assertEqual(last_request_body['redirect_urls']['return_url'], expected)

                success_log_message = 'Successfully created PayPal payment [{}] for basket [{}].'.format(
                    self.PAYMENT_ID, self.basket.id
                )
                paypal_logger.check(
                    (
                        logger_name,
                        'WARNING',
                        failure_log_message,
                    ),
                    (
                        logger_name,
                        'INFO',
                        success_log_message
                    )
                )

    @responses.activate
    def test_get_transaction_parameters(self):
        """Verify the processor returns the appropriate parameters required to complete a transaction."""
        self.mock_oauth2_response()
        response = self.mock_payment_creation_response(self.basket)

        self._assert_transaction_parameters()
        self.assert_processor_response_recorded(self.processor.NAME, self.PAYMENT_ID, response, basket=self.basket)

        last_request_body = json.loads(responses.calls[-1].request.body)
        expected = urljoin(self.site.siteconfiguration.build_ecommerce_url(), reverse('paypal:execute'))
        self.assertEqual(last_request_body['redirect_urls']['return_url'], expected)

    @responses.activate
    def test_get_courseid_title(self):
        for line in self.basket.all_lines():
            self.assertEqual(
                'a/b/c|Seat in Demo Course with test-certificate-type certificate',
                self.processor.get_courseid_title(line)
            )

    @responses.activate
    def test_get_transaction_parameters_with_retry(self):
        """Verify the processor returns the appropriate parameters required to complete a transaction after a retry"""
        response_error = self.get_payment_creation_error_response_mock()
        response_success = self.get_payment_creation_response_mock(self.basket)
        api_responses = [
            {'body': response_error, 'status': 200},
            {'body': response_success, 'status': 200}
        ]
        self._assert_transaction_parameters_retry(
            api_responses,
            response_success,
            'Creating PayPal payment for basket [{}] was unsuccessful. Will retry.'.format(self.basket.id)
        )

    @responses.activate
    def test_get_transaction_parameters_server_error_with_retry(self):
        """
        Verify the processor returns the appropriate parameters required
        to complete a transaction after a retry with server error
        """
        response_error = self.get_payment_creation_error_response_mock()
        response_success = self.get_payment_creation_response_mock(self.basket)

        api_responses = [
            {'body': response_error, 'status': 500},
            {'body': response_success, 'status': 200}
        ]
        self._assert_transaction_parameters_retry(
            api_responses,
            response_success,
            'Creating PayPal payment for basket [{}] resulted in an exception. Will retry.'.format(self.basket.id)
        )

    @mock.patch('ecommerce.extensions.payment.processors.paypal.paypalrestsdk.Payment')
    @ddt.data(None, Paypal.DEFAULT_PROFILE_NAME, 'some-other-name')
    def test_dummy_web_profiles(self, enabled_profile_name, mock_payment):
        """
        Verify that the payment creation payload references a web profile when one is enabled with the expected name.
        This should occur when the create_and_set_webprofile waffle is disabled.
        """
        toggle_switch('create_and_set_webprofile', False)
        mock_payment_instance = mock.Mock()
        # NOTE: This is necessary to avoid the issue in https://code.djangoproject.com/ticket/25493.
        mock_payment_instance.id = FuzzyInteger(low=1).fuzz()
        mock_payment_instance.to_dict.return_value = {}
        mock_payment_instance.links = [mock.Mock(rel='approval_url', href='dummy')]
        mock_payment.return_value = mock_payment_instance

        if enabled_profile_name is not None:
            PaypalWebProfile.objects.create(name=enabled_profile_name, id='test-profile-id')

        self.processor.get_transaction_parameters(self.basket, request=self.request)
        payment_creation_payload = mock_payment.call_args[0][0]
        if enabled_profile_name == Paypal.DEFAULT_PROFILE_NAME:
            self.assertEqual(payment_creation_payload['experience_profile_id'], 'test-profile-id')
        else:
            self.assertNotIn('experience_profile_id', payment_creation_payload)

    @mock.patch('ecommerce.extensions.payment.processors.paypal.logger')
    @mock.patch('ecommerce.extensions.payment.processors.paypal.paypalrestsdk.Payment')
    @mock.patch('ecommerce.extensions.payment.processors.paypal.paypalrestsdk.WebProfile')
    def test_web_profile_with_valid_locale(self, mock_web_profile, mock_payment, mock_logger):
        """
        Verify that the payment creation payload references a web profile when a valid locale is chosen
        This should occur when the create_and_set_webprofile waffle is enabled.
        """
        toggle_switch('create_and_set_webprofile', True)
        mock_payment_instance = mock.Mock()
        # NOTE: This is necessary to avoid the issue in https://code.djangoproject.com/ticket/25493.
        mock_payment_instance.id = FuzzyInteger(low=1).fuzz()
        mock_payment_instance.to_dict.return_value = {}
        mock_payment_instance.links = [mock.Mock(rel='approval_url', href='dummy')]
        mock_payment.return_value = mock_payment_instance

        Paypal.resolve_paypal_locale = mock.Mock(return_value='valid_locale')
        mock_web_profile_instance = mock.Mock()
        mock_web_profile_instance.id = 'test-profile-id'
        mock_web_profile_instance.presentation.locale_code = 'valid_locale'
        mock_web_profile.create = mock.Mock(return_value=True)
        mock_web_profile.return_value = mock_web_profile_instance

        self.processor.get_transaction_parameters(self.basket, request=self.request)
        payment_creation_payload = mock_payment.call_args[0][0]
        self.assertEqual(payment_creation_payload['experience_profile_id'], 'test-profile-id')

        msg = 'Web Profile[%s] for locale %s created successfully' % (
            mock_web_profile_instance.id,
            mock_web_profile_instance.presentation.locale_code
        )
        mock_logger.info.assert_any_call(msg)

    @mock.patch('ecommerce.extensions.payment.processors.paypal.logger')
    @mock.patch('ecommerce.extensions.payment.processors.paypal.paypalrestsdk.Payment')
    @mock.patch('ecommerce.extensions.payment.processors.paypal.paypalrestsdk.WebProfile')
    def test_web_profile_with_invalid_locale(self, mock_web_profile, mock_payment, mock_logger):
        """
        Verify that the payment creation payload does not reference a web profile when an invalid locale is chosen.
        This should occur when the create_and_set_webprofile waffle is enabled.
        """
        toggle_switch('create_and_set_webprofile', True)
        mock_payment_instance = mock.Mock()
        # NOTE: This is necessary to avoid the issue in https://code.djangoproject.com/ticket/25493.
        mock_payment_instance.id = FuzzyInteger(low=1).fuzz()
        mock_payment_instance.to_dict.return_value = {}
        mock_payment_instance.links = [mock.Mock(rel='approval_url', href='dummy')]
        mock_payment.return_value = mock_payment_instance

        Paypal.resolve_paypal_locale = mock.Mock(return_value='invalid_locale')
        mock_web_profile_instance = mock.Mock()
        mock_web_profile_instance.create = mock.Mock(return_value=False)
        mock_web_profile_instance.error = 'invalid_config'
        mock_web_profile.return_value = mock_web_profile_instance

        self.processor.get_transaction_parameters(self.basket, request=self.request)
        payment_creation_payload = mock_payment.call_args[0][0]
        self.assertNotIn('experience_profile_id', payment_creation_payload)

        msg = 'Web profile creation encountered error [%s]. Will continue without one' % (
            mock_web_profile_instance.error
        )
        mock_logger.warning.assert_any_call(msg)

    @mock.patch('ecommerce.extensions.payment.processors.paypal.logger')
    @mock.patch('ecommerce.extensions.payment.processors.paypal.paypalrestsdk.Payment')
    @mock.patch('ecommerce.extensions.payment.processors.paypal.paypalrestsdk.WebProfile.__init__')
    def test_web_profile_with_exception(self, mock_web_profile_init, mock_payment, mock_logger):
        """
        Verify that the payment creation payload does not reference a web profile if its creation results in exception.
        This should occur when the create_and_set_webprofile waffle is enabled.
        """
        toggle_switch('create_and_set_webprofile', True)
        mock_payment_instance = mock.Mock()
        # NOTE: This is necessary to avoid the issue in https://code.djangoproject.com/ticket/25493.
        mock_payment_instance.id = FuzzyInteger(low=1).fuzz()
        mock_payment_instance.to_dict.return_value = {}
        mock_payment_instance.links = [mock.Mock(rel='approval_url', href='dummy')]
        mock_payment.return_value = mock_payment_instance

        Paypal.resolve_paypal_locale = mock.Mock(return_value="valid_locale")
        mock_web_profile_init.side_effect = Exception('MissingConfig Exception')

        self.processor.get_transaction_parameters(self.basket, request=self.request)
        payment_creation_payload = mock_payment.call_args[0][0]
        self.assertNotIn('experience_profile_id', payment_creation_payload)
        with self.assertRaises(Exception) as ex:
            self.assertEqual(ex.message, 'MissingConfig Exception')

        msg = 'Creating PayPal WebProfile resulted in exception. Will continue without one.'
        mock_logger.warning.assert_any_call(msg)

    @ddt.unpack
    @ddt.data(
        ['zh', 'en', 'US'],
        ['zh', 'es', 'MX'],
        ['zh', 'es-419', 'MX'],
        ['zh', 'invalid', 'CN'],
        ['zh-zh', '', 'CN'],
        ['invalid default', 'invalid cookie', None]
    )
    @mock.patch('ecommerce.extensions.payment.processors.paypal.Paypal.create_temporary_web_profile')
    def test_resolve_paypal_locale(self, default_locale, cookie_locale, expected_paypal_locale, mock_method):
        """
        Verify that the correct locale for payment processing is fetched from the language cookie
        """
        translation.activate(default_locale)
        mock_method.side_effect = Exception("End of test")  # Force test to end after this call

        toggle_switch('create_and_set_webprofile', True)
        self.request.COOKIES[settings.LANGUAGE_COOKIE_NAME] = cookie_locale
        try:
            self.processor.get_transaction_parameters(self.basket, request=self.request)
        except Exception:  # pylint: disable=broad-except
            pass
        mock_method.assert_called_with(expected_paypal_locale)

    @responses.activate
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

    @responses.activate
    def test_payment_creation_exception_state(self):
        """Verify that an exception is thrown while create a payment results in paypal exception."""
        self.mock_oauth2_response()
        response_error = self.get_payment_creation_error_response_mock()
        self.mock_api_response('/v1/payments/payment', response_error, status=500)
        logger_name = 'ecommerce.extensions.payment.processors.paypal'

        with LogCapture(logger_name) as paypal_logger:
            self.assertRaises(
                paypalrestsdk.exceptions.ServerError,
                self.processor.get_transaction_parameters,
                self.basket,
                request=self.request
            )
            msg = 'After {} retries, creating PayPal payment for basket [{}] still experienced exception.'.format(
                self.processor.retry_attempts + 1, self.basket.id)
            paypal_logger.check(
                (
                    logger_name,
                    'ERROR',
                    msg
                )
            )

    @responses.activate
    def test_approval_url_missing(self):
        """Verify that a missing approval URL results in a GatewayError."""
        self.mock_oauth2_response()
        response = self.mock_payment_creation_response(self.basket, approval_url=None)

        self.assertRaises(GatewayError, self.processor.get_transaction_parameters, self.basket, request=self.request)
        self.assert_processor_response_recorded(self.processor.NAME, self.PAYMENT_ID, response, basket=self.basket)

    @responses.activate
    def test_handle_processor_response(self):
        """Verify that the processor creates the appropriate PaymentEvent and Source objects."""
        for payer_info in (PaypalMixin.PAYER_INFO, {"shipping_address": None}):
            responses.reset()
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

    @responses.activate
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

    @responses.activate
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
        Tests issuing credit/refund with Paypal processor
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
                actual_transaction_id = self.processor.issue_credit(order.number, order.basket, source.reference,
                                                                    amount, currency)
                self.assertEqual(actual_transaction_id, transaction_id)

        # Verify PaymentProcessorResponse created
        self.assert_processor_response_recorded(self.processor.NAME, transaction_id, {'id': transaction_id}, basket)

    def test_issue_credit_error(self):
        """
        Tests issue credit/refund fails in case of erroneous response or exceptions
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
                self.assertRaises(GatewayError, self.processor.issue_credit, order.number, order.basket,
                                  source.reference, amount, currency)
                self.assertEqual(source.amount_refunded, 0)

        # Test error response
        with mock.patch.object(paypalrestsdk.Payment, 'find', return_value=payment):
            with mock.patch.object(paypalrestsdk.Sale, 'refund', return_value=paypal_refund):
                self.assertRaises(GatewayError, self.processor.issue_credit, order.number, order.basket,
                                  source.reference, amount, currency)

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
