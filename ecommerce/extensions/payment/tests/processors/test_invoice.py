# -*- coding: utf-8 -*-
"""Unit tests of Invoice payment processor implementation."""
from __future__ import unicode_literals

from oscar.test import factories

from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.processors.invoice import InvoicePayment
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.tests.testcases import TestCase


class InvoiceTests(PaymentProcessorTestCaseMixin, TestCase):
    """ Tests for Invoice payment processor. """

    processor_class = InvoicePayment
    processor_name = 'invoice'

    def test_configuration(self):  # pylint: disable=arguments-differ
        """
        Tests configuration
        """
        self.skipTest('Invoice processor does not currently require configuration.')

    def test_handle_processor_response(self):
        """ Verify the processor creates the appropriate PaymentEvent and Source objects. """

        order = factories.OrderFactory()

        source, payment_event = self.processor_class().handle_processor_response({}, order)

        # Validate PaymentEvent
        self.assertEqual(payment_event.event_type.name, PaymentEventTypeName.PAID)

        # Validate PaymentSource
        self.assertEqual(source.source_type.name, self.processor.NAME)

    def test_get_transaction_parameters(self):
        """
        Tests that transaction parameters are always None
        """
        params = self.processor_class().get_transaction_parameters(self.basket)
        self.assertIsNone(None, params)

    def test_issue_credit(self):
        """Test issue credit"""
        self.assertRaises(NotImplementedError, self.processor_class().issue_credit, None, 0, 'USD')

    def test_issue_credit_error(self):
        """ Tests that Invoice payment processor does not support issuing credit """
        self.skipTest('Invoice processor does not yet support issuing credit.')
