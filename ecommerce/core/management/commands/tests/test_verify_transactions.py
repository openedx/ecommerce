"""
Tests for Django management command to verify ecommerce transactions.
"""
import datetime

import pytz
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from oscar.core.loading import get_class, get_model
from oscar.test.factories import OrderFactory

from ecommerce.core.management.commands.tests.factories import PaymentEventFactory
from ecommerce.core.management.commands.verify_transactions import DEFAULT_END_DELTA_TIME, DEFAULT_START_DELTA_TIME

Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentEventTypeName = get_class('order.constants', 'PaymentEventTypeName')


class VerifyTransactionsTest(TestCase):

    def setUp(self):
        # Timestamp in the middle of the time window
        time_delta = (DEFAULT_START_DELTA_TIME + DEFAULT_END_DELTA_TIME) / 2
        self.timestamp = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=time_delta)

        self.payevent = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.PAID)
        self.refundevent = PaymentEventType.objects.get_or_create(name=PaymentEventTypeName.REFUNDED)
        self.order = OrderFactory(total_incl_tax=90, date_placed=self.timestamp)
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
        except CommandError:
            self.fail("Failed to verify transactions when no errors were expected.")

    def test_no_errors(self):
        """Test verify_transactions with order and payment of same amount."""
        payment = PaymentEventFactory(order=self.order,
                                      amount=90,
                                      event_type_id=self.payevent[0].id,
                                      date_created=self.timestamp)
        payment.save()
        refund = PaymentEventFactory(order=self.order,
                                     amount=90,
                                     event_type_id=self.refundevent[0].id,
                                     date_created=self.timestamp)
        refund.save()
        try:
            call_command('verify_transactions')
        except CommandError:
            self.fail("Failed to verify transactions when no errors were expected.")

    def test_no_payment_for_order(self):
        """Verify errors are thrown when there are orders without payments."""
        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions')
        exception = cm.exception
        self.assertIn("The following orders are without payments", exception.message)
        self.assertIn(str(self.order.id), exception.message)

    def test_two_same_payments_for_order(self):
        """ Verify that errors are thrown when their are multiple payments on an order."""
        payment1 = PaymentEventFactory(order=self.order,
                                       amount=90,
                                       event_type_id=self.payevent[0].id,
                                       date_created=self.timestamp)
        payment2 = PaymentEventFactory(order=self.order,
                                       amount=90,
                                       event_type_id=self.payevent[0].id,
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
                                       event_type_id=self.payevent[0].id,
                                       date_created=self.timestamp)
        payment2 = PaymentEventFactory(order=self.order,
                                       amount=90,
                                       event_type_id=self.payevent[0].id,
                                       date_created=self.timestamp)
        payment3 = PaymentEventFactory(order=self.order,
                                       amount=90,
                                       event_type_id=self.payevent[0].id,
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
                                      event_type_id=self.payevent[0].id,
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
