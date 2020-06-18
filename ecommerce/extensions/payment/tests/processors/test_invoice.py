# -*- coding: utf-8 -*-
"""Unit tests of Invoice payment processor implementation."""


import datetime

import pytz
from oscar.test import factories

from ecommerce.core.models import BusinessClient
from ecommerce.extensions.api.serializers import InvoiceSerializer
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
        """ Verify the processor creates the appropriate PaymentEvent, Source and Invoice objects. """

        order = factories.OrderFactory()
        business_client = BusinessClient.objects.create(name='Test client')
        source, payment_event = self.processor_class(self.site).handle_processor_response({}, order, business_client)

        # Validate PaymentEvent
        self.assertEqual(payment_event.event_type.name, PaymentEventTypeName.PAID)
        self.assertTrue(Invoice.objects.get(order=order, business_client=business_client))

        # Validate PaymentSource
        self.assertEqual(source.source_type.name, self.processor.NAME)

    def test_get_transaction_parameters(self):
        """
        Tests that transaction parameters are always None
        """
        # pylint: disable=assignment-from-none
        params = self.processor_class(self.site).get_transaction_parameters(self.basket)
        self.assertIsNone(None, params)

    def test_issue_credit(self):
        """Test issue credit"""
        self.assertRaises(NotImplementedError, self.processor_class(self.site).issue_credit, None, None, None, 0, 'USD')

    def test_issue_credit_error(self):
        """ Tests that Invoice payment processor does not support issuing credit """
        self.skipTest('Invoice processor does not yet support issuing credit.')

    def test_invoice_creation(self):
        """ Verify the invoice object is created properly. """
        order = factories.OrderFactory()
        business_client = BusinessClient.objects.create(name='Test client')
        invoice_data = {
            'number': 'INV-001',
            'type': Invoice.PREPAID,
            'payment_date': datetime.datetime(2016, 1, 1, tzinfo=pytz.UTC).isoformat(),
            'tax_deducted_source': 25,
        }

        self.processor_class(self.site).handle_processor_response({}, order, business_client, invoice_data)
        invoice = Invoice.objects.latest()
        self.assertEqual(invoice.order, order)
        self.assertEqual(invoice.business_client, business_client)
        serialized_invoice = InvoiceSerializer(invoice).data
        for data in invoice_data:
            if data == 'payment_date':
                self.assertEqual(invoice.payment_date.isoformat(), invoice_data[data])
            else:
                self.assertEqual(serialized_invoice[data], invoice_data[data])
