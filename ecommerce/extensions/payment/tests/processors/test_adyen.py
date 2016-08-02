# -*- coding: utf-8 -*-
"""Unit tests of Adyen payment processor implementation."""
from __future__ import unicode_literals
import logging
import ddt

import httpretty
from oscar.apps.payment.exceptions import GatewayError, TransactionDeclined
from oscar.core.loading import get_model
from testfixtures import LogCapture

from ecommerce.extensions.payment.exceptions import (
    MissingAdyenEventCodeException,
    UnsupportedAdyenEventException
)
from ecommerce.extensions.payment.processors.adyen import Adyen
from ecommerce.extensions.payment.tests.mixins import AdyenMixin
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.tests.testcases import TestCase


log = logging.getLogger(__name__)

PaymentEventType = get_model('order', 'PaymentEventType')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')
SourceType = get_model('payment', 'SourceType')


@ddt.ddt
class AdyenTests(AdyenMixin, PaymentProcessorTestCaseMixin, TestCase):
    """Tests for the Adyen payment processor."""

    processor_class = Adyen
    processor_name = 'adyen'

    def _assert_transaction_parameters(self):
        """DRY helper for verifying transaction parameters."""
        expected = {
            'payment_page_url': '',
        }
        actual = self.processor.get_transaction_parameters(self.basket, request=self.request)
        self.assertEqual(actual, expected)

    def _assert_payment_event_and_source(self, payment_response):
        """DRY helper for verifying a payment event and source."""
        source, payment_event = self.processor.handle_processor_response(
            payment_response,
            basket=self.basket
        )

        # Validate Source
        source_type = SourceType.objects.get(code=self.processor.NAME)
        reference = self.ADYEN_PAYMENT_REFERENCE
        self.assert_basket_matches_source(self.basket, source, source_type, reference)

        # Validate PaymentEvent
        paid_type = PaymentEventType.objects.get(code='paid')
        amount = self.basket.total_incl_tax
        self.assert_valid_payment_event_fields(payment_event, amount, paid_type, self.processor.NAME, reference)

    @httpretty.activate
    def test_get_transaction_parameters(self):
        """Verify the processor returns the appropriate parameters required to complete a transaction."""
        self.mock_payment_creation_response(self.basket)
        self._assert_transaction_parameters()

    @httpretty.activate
    def test_payment_refused_creation_state(self):
        """Verify that failure to create a payment."""
        response = self.mock_payment_creation_response(self.basket, payment_refused=True)
        self.assertEqual(response['eventCode'], 'AUTHORISATION')
        self.assertEqual(response['resultCode'], 'Refused')

    @httpretty.activate
    def test_handle_processor_response(self):
        """Verify that the processor creates the appropriate PaymentEvent and Source objects."""
        adyen_payment_response = self.mock_payment_creation_response(self.basket)

        self._assert_payment_event_and_source(adyen_payment_response)

    @httpretty.activate
    def test_handle_processor_response_refused_payment(self):
        """Verify that the processor raises exception in case of refused payment."""
        adyen_payment_response = self.mock_payment_creation_response(self.basket, payment_refused=True)

        with self.assertRaises(TransactionDeclined):
            self.processor.handle_processor_response(
                adyen_payment_response,
                basket=self.basket
            )

    @httpretty.activate
    def test_handle_processor_response_error(self):
        """
        Tests handle processorresponse fails in case of erroneous responses.
        """
        adyen_payment_response = self.mock_payment_creation_response(
            self.basket, True, self.ADYEN_PAYMENT_INVALID_EVENT
        )
        with self.assertRaises(UnsupportedAdyenEventException):
            self.processor.handle_processor_response(
                adyen_payment_response,
                basket=self.basket
            )

        adyen_payment_response = self.mock_payment_creation_response(
            self.basket, True, self.ADYEN_PAYMENT_INVALID_RESPONSE
        )
        with self.assertRaises(MissingAdyenEventCodeException):
            self.processor.handle_processor_response(
                adyen_payment_response,
                basket=self.basket
            )

    @httpretty.activate
    def test_issue_credit(self):
        """
        Tests issuing credit with Adyen processor.
        """
        refund = self.create_refund(self.processor_name)
        order = refund.order
        basket = order.basket
        amount = refund.total_credit_excl_tax
        currency = refund.currency
        source = order.sources.first()

        adyen_refund_response = self.mock_refund_creation_response(self.basket)
        transaction_id = self.ADYEN_REDUND_REFERENCE
        self.processor.issue_credit(source, amount, currency)
        self.assert_processor_response_recorded(self.processor.NAME, transaction_id, adyen_refund_response, basket)

    @httpretty.activate
    def test_issue_credit_error(self):
        """
        Tests issue credit fails in case of erroneous response or exceptions.
        """
        refund = self.create_refund(self.processor_name)
        order = refund.order
        amount = refund.total_credit_excl_tax
        currency = refund.currency
        source = order.sources.first()

        # Error case with invalid Adyen refund response
        self.mock_refund_creation_response(self.basket, True, self.ADYEN_REFUND_INVALID_RESPONSE)
        with self.assertRaises(GatewayError):
            self.processor.issue_credit(source, amount, currency)

        # Verify Source unchanged
        self.assertEqual(source.amount_refunded, 0)

        # Error case with invalid Adyen refund response code
        self.mock_refund_creation_response(self.basket, True, self.ADYEN_REFUND_INVALID_RESPONSE, 400)
        with self.assertRaises(GatewayError):
            logger_name = 'ecommerce.extensions.payment.processors.adyen'
            with LogCapture(logger_name) as adyen_logger:
                self.processor.issue_credit(source, amount, currency)
                adyen_logger.check(
                    (
                        logger_name, 'ERROR',
                        u'An error occurred while attempting to issue a credit (via Adyen) for order [{}].'.format(
                            order.number
                        )
                    )
                )

        # Verify Source unchanged
        self.assertEqual(source.amount_refunded, 0)
