"""
Tests for Django management command to verify ecommerce transactions.
"""
import datetime

import pytz
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from oscar.core.loading import get_class, get_model
from oscar.test.factories import OrderFactory, OrderLineFactory, ProductFactory

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.core.management.commands.tests.factories import PaymentEventFactory
from ecommerce.core.management.commands.verify_transactions import DEFAULT_END_DELTA_TIME, DEFAULT_START_DELTA_TIME

PaymentEventType = get_model('order', 'PaymentEventType')
PaymentEventTypeName = get_class('order.constants', 'PaymentEventTypeName')
ProductClass = get_model('catalogue', 'ProductClass')


class VerifyTransactionsTest(TestCase):

    def setUp(self):
        # Timestamp in the middle of the time window
        time_delta = (DEFAULT_START_DELTA_TIME + DEFAULT_END_DELTA_TIME) / 2
        self.timestamp = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=time_delta)

        self.payevent, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.PAID)
        self.refundevent, __ = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.REFUNDED)
        self.seat_product_class, __ = ProductClass.objects.get_or_create(name=SEAT_PRODUCT_CLASS_NAME)
        self.order = OrderFactory(total_incl_tax=90, date_placed=self.timestamp)
        self.product = ProductFactory(product_class=self.seat_product_class, categories=None)
        self.line = OrderLineFactory(order=self.order, product=self.product)
        self.line.save()
        self.product.save()
        self.order.save()

    def test_time_window(self):
        """Test verify_transactions only examines the correct time window"""
        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions')
        exception = cm.exception
        self.assertIn("The following orders are without payments", exception.message)
        self.assertIn(str(self.order.id), exception.message)

        time_outside_window = DEFAULT_START_DELTA_TIME + DEFAULT_END_DELTA_TIME + 1
        time_outside_window_datetime = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=time_outside_window)
        self.order.date_placed = time_outside_window_datetime
        self.order.save()

        try:
            call_command('verify_transactions')
        except CommandError as e:
            self.fail("Failed to verify transactions when no errors were expected. " + e.message)

    def test_no_errors(self):
        """Test verify_transactions with order and payment of same amount."""
        payment = PaymentEventFactory(order=self.order,
                                      amount=90,
                                      event_type_id=self.payevent.id,
                                      date_created=self.timestamp)
        payment.save()
        refund = PaymentEventFactory(order=self.order,
                                     amount=90,
                                     event_type_id=self.refundevent.id,
                                     date_created=self.timestamp)
        refund.save()
        try:
            call_command('verify_transactions')
        except CommandError as e:
            self.fail("Failed to verify transactions when no errors were expected. " + e.message)

    def test_zero_dollar_order(self):
        """Verify zero dollar orders are not flagged as errors."""
        total_incl_tax_before = self.order.total_incl_tax
        self.order.total_incl_tax = 0
        self.order.save()
        try:
            call_command('verify_transactions')
        except CommandError as e:
            self.fail("Failed to verify transactions when no errors were expected. " + e.message)
        finally:
            self.order.total_incl_tax = total_incl_tax_before
            self.order.save()

    def test_no_payment_for_valid_product_order(self):
        """Verify errors are thrown when there are valid product orders without payments."""
        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions')
        exception = cm.exception
        self.assertIn("The following orders are without payments", exception.message)
        self.assertIn(str(self.order.id), exception.message)

    def test_no_payment_for_filtered_product_order(self):
        """Verify errors are not thrown when there are filtered product orders without payments."""
        new_product_class, __ = ProductClass.objects.get_or_create(name="Test Product Class")
        self.product.product_class = new_product_class
        self.product.save()

        try:
            call_command('verify_transactions')
        except CommandError as e:
            self.fail("Failed to verify transactions when no errors were expected. " + e.message)
        finally:
            self.product.product_class = self.seat_product_class
            self.product.save()

    def test_two_same_payments_for_order(self):
        """ Verify that errors are thrown when their are multiple payments on an order."""
        payment1 = PaymentEventFactory(order=self.order,
                                       amount=90,
                                       event_type_id=self.payevent.id,
                                       date_created=self.timestamp)
        payment2 = PaymentEventFactory(order=self.order,
                                       amount=90,
                                       event_type_id=self.payevent.id,
                                       date_created=self.timestamp)
        payment1.save()
        payment2.save()
        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions')
        exception = cm.exception
        self.assertIn("The following orders had multiple payments ", exception.message)
        self.assertIn(str(self.order.id), exception.message)
        self.assertIn(str(payment1.id), exception.message)
        self.assertIn(str(payment2.id), exception.message)

    def test_multiple_payments_for_order(self):
        """ Verify that errors are thrown when their are multiple payments on an order."""
        payment1 = PaymentEventFactory(order=self.order,
                                       amount=90,
                                       event_type_id=self.payevent.id,
                                       date_created=self.timestamp)
        payment2 = PaymentEventFactory(order=self.order,
                                       amount=90,
                                       event_type_id=self.payevent.id,
                                       date_created=self.timestamp)
        payment3 = PaymentEventFactory(order=self.order,
                                       amount=90,
                                       event_type_id=self.payevent.id,
                                       date_created=self.timestamp)
        payment1.save()
        payment2.save()
        payment3.save()
        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions')
        exception = cm.exception
        self.assertIn("The following orders had multiple payments ", exception.message)
        self.assertIn(str(self.order.id), exception.message)
        self.assertIn(str(payment1.id), exception.message)
        self.assertIn(str(payment2.id), exception.message)
        self.assertIn(str(payment3.id), exception.message)

    def test_totals_mismatch(self):
        """ Verify errors thrown when payment and order totals don't match."""
        payment = PaymentEventFactory(order=self.order,
                                      amount=100,
                                      event_type_id=self.payevent.id,
                                      date_created=self.timestamp)
        payment.save()
        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions')
        exception = cm.exception
        self.assertIn("Order totals mismatch with payments received", exception.message)
        self.assertIn(str(self.order.id), exception.message)
        self.assertIn(str(payment.id), exception.message)
        self.assertIn("Amount: 90.00", exception.message)
        self.assertIn("Amount: 100.00", exception.message)
        self.assertIn("Amount: 100.00", exception.message)

    def test_refund_exceeded(self):
        """Test verify_transactions with refund which exceed amount paid."""
        payment = PaymentEventFactory(order=self.order,
                                      amount=90,
                                      event_type_id=self.payevent.id,
                                      date_created=self.timestamp)
        payment.save()
        refund = PaymentEventFactory(order=self.order,
                                     amount=100,
                                     event_type_id=self.refundevent.id,
                                     date_created=self.timestamp)
        refund.save()
        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions')
        exception = cm.exception
        self.assertIn("The following orders had excessive refunds", exception.message)
        self.assertIn(str(self.order.id), exception.message)
        self.assertIn(str(refund.id), exception.message)
        self.assertIn("Amount: 90.00", exception.message)
        self.assertIn("Amount: 100.00", exception.message)
