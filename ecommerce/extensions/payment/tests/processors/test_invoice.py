# -*- coding: utf-8 -*-
"""Unit tests of Invoice payment processor implementation."""
from __future__ import unicode_literals

import datetime

from oscar.test import factories
import pytz

from ecommerce.core.models import BusinessClient
from ecommerce.extensions.order.constants import PaymentEventTypeName
from ecommerce.extensions.payment.processors.invoice import InvoicePayment
from ecommerce.extensions.payment.tests.processors.mixins import PaymentProcessorTestCaseMixin
from ecommerce.invoice.models import Invoice
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
        """ Verify the processor creates the appropriate PaymentEvent and Source objects and an Invoice is created """
        order = factories.OrderFactory()
        business_client = BusinessClient.objects.create(name='Test client')
        source, payment_event = self.processor_class().handle_processor_response({}, order, business_client)

        self.assertEqual(payment_event.event_type.name, PaymentEventTypeName.PAID)
        self.assertEqual(source.source_type.name, self.processor.NAME)
        self.assertTrue(Invoice.objects.filter(business_client=business_client, order=order))

    def test_prepaid_invoice(self):
        """ Verify a prepaid invoice object is created. """
        order = factories.OrderFactory()
        business_client = BusinessClient.objects.create(name='Test client')
        invoice_data = {
            'invoice_type': Invoice.PREPAID,
            'invoice_number': 'EDX-0001',
            'invoiced_amount': 100,
            'invoice_payment_date': pytz.utc.localize(datetime.datetime(2020, 01, 01)),
            'tax_deducted_source': False,
            'tax_deducted_source_value': False,
            'invoice_discount_type': None,
            'invoice_discount_value': None
        }
        self.processor_class().handle_processor_response(
            {}, order, business_client, invoice_data
        )
        invoice = Invoice.objects.latest()
        self.assertEqual(invoice.order, order)
        self.assertEqual(invoice.business_client, business_client)
        self.assertEqual(invoice.invoice_type, invoice_data['invoice_type'])
        self.assertEqual(invoice.number, invoice_data['invoice_number'])
        self.assertEqual(invoice.invoiced_amount, invoice_data['invoiced_amount'])
        self.assertEqual(invoice.invoice_payment_date, invoice_data['invoice_payment_date'])
        self.assertEqual(invoice.tax_deducted_source, invoice_data['tax_deducted_source'])
        self.assertEqual(invoice.tax_deducted_source_value, invoice_data['tax_deducted_source_value'])
        self.assertEqual(invoice.invoice_discount_type, invoice_data['invoice_discount_type'])
        self.assertEqual(invoice.invoice_discount_value, invoice_data['invoice_discount_value'])

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
