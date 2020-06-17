"""
Tests for Django management command to verify ecommerce transactions.
"""


import datetime

import ddt
import pytz
from django.core.management import call_command
from django.core.management.base import CommandError
from oscar.core.loading import get_class, get_model
from oscar.test.factories import OrderFactory, OrderLineFactory, ProductFactory

from ecommerce.core.constants import SEAT_PRODUCT_CLASS_NAME
from ecommerce.core.management.commands.tests.factories import PaymentEventFactory
from ecommerce.core.management.commands.verify_transactions import DEFAULT_END_DELTA_TIME, DEFAULT_START_DELTA_TIME
from ecommerce.tests.testcases import TestCase

PaymentEventType = get_model('order', 'PaymentEventType')
PaymentEventTypeName = get_class('order.constants', 'PaymentEventTypeName')
ProductClass = get_model('catalogue', 'ProductClass')


@ddt.ddt
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
        self.line = OrderLineFactory(order=self.order, product=self.product, partner_sku='test_sku')
        self.line.save()
        self.product.save()
        self.order.save()

    def test_time_window(self):
        """ Test verify_transactions only examines the correct time window """
        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions')
        exception = str(cm.exception)
        self.assertIn("The following orders are without payments", exception)
        self.assertIn(str(self.order.id), exception)

        time_outside_window = DEFAULT_START_DELTA_TIME + DEFAULT_END_DELTA_TIME + 1
        time_outside_window_datetime = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=time_outside_window)
        self.order.date_placed = time_outside_window_datetime
        self.order.save()

        try:
            call_command('verify_transactions')
        except CommandError as e:
            self.fail("Failed to verify transactions when no errors were expected. {}".format(e))

    def test_threshold(self):
        """ Test verify_transactions only fails if there are too many anomolies """
        for i in range(3):
            # Create some "good" orders w/ payments
            order = OrderFactory(total_incl_tax=50 + i, date_placed=self.timestamp)
            line = OrderLineFactory(order=order, product=self.product, partner_sku='test_sku')
            payment = PaymentEventFactory(
                order=order,
                amount=50 + i,
                event_type_id=self.payevent.id,
                date_created=self.timestamp
            )
            payment.save()
            line.save()
            order.save()

        # self.order fixture should still have no payment
        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions')
        exception = str(cm.exception)
        self.assertIn("The following orders are without payments", exception)
        self.assertIn(str(self.order.id), exception)

        try:
            call_command('verify_transactions', '--threshold=1')  # allow 1 anomoly
        except CommandError as e:
            self.fail("Failed to verify transactions when no failure was expected. {}".format(e))

        try:
            call_command('verify_transactions', '--threshold=0.25')  # 1-in-4 should be just on the line
        except CommandError as e:
            self.fail("Failed to verify transactions when no failure was expected. {}".format(e))

        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions', '--threshold=0.2')
        exception = str(cm.exception)
        self.assertIn("The following orders are without payments", exception)
        self.assertIn(str(self.order.id), exception)

    def test_no_errors(self):
        """ Test verify_transactions with order and payment of same amount """
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
            self.fail("Failed to verify transactions when no errors were expected. {}".format(e))

    def test_zero_dollar_order(self):
        """ Verify zero dollar orders are not flagged as errors """
        total_incl_tax_before = self.order.total_incl_tax
        self.order.total_incl_tax = 0
        self.order.save()
        try:
            call_command('verify_transactions')
        except CommandError as e:
            self.fail("Failed to verify transactions when no errors were expected. {}".format(e))
        finally:
            self.order.total_incl_tax = total_incl_tax_before
            self.order.save()

    def test_no_payment_for_valid_product_order(self):
        """ Verify errors are thrown when there are valid product orders without payments """
        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions')
        exception = str(cm.exception)
        self.assertIn("The following orders are without payments", exception)
        self.assertIn(str(self.order.id), exception)

    def test_no_payment_for_filtered_product_order(self):
        """ Verify errors are not thrown when there are filtered product orders without payments """
        new_product_class, __ = ProductClass.objects.get_or_create(name="Test Product Class")
        self.product.product_class = new_product_class
        self.product.save()

        try:
            call_command('verify_transactions')
        except CommandError as e:
            self.fail("Failed to verify transactions when no errors were expected. {}".format(e))
        finally:
            self.product.product_class = self.seat_product_class
            self.product.save()

    def test_two_same_payments_for_order(self):
        """ Verify that errors are thrown when their are multiple payments on an order """
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
        exception = str(cm.exception)
        self.assertIn("The following orders had multiple payments", exception)
        self.assertIn(str(self.order.id), exception)
        self.assertIn(str(payment1.id), exception)
        self.assertIn(str(payment2.id), exception)

    def test_multiple_payments_for_order(self):
        """ Verify that errors are thrown when their are multiple payments on an order """
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
        exception = str(cm.exception)
        self.assertIn("The following orders had multiple payments", exception)
        self.assertIn(str(self.order.id), exception)
        self.assertIn(str(payment1.id), exception)
        self.assertIn(str(payment2.id), exception)
        self.assertIn(str(payment3.id), exception)

    @ddt.data(80, 100)
    def test_totals_mismatch(self, amount):
        """ Verify errors thrown when payment and order totals don't match """
        payment = PaymentEventFactory(order=self.order,
                                      amount=amount,
                                      event_type_id=self.payevent.id,
                                      date_created=self.timestamp)
        payment.save()
        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions')
        exception = str(cm.exception)
        self.assertIn("The following order totals mismatch payments received", exception)
        self.assertIn(str(self.order.id), exception)
        self.assertIn(str(payment.id), exception)
        self.assertIn('"amount": 90.0', exception)
        self.assertIn('"amount": {}'.format(amount), exception)

    def test_totals_mismatch_support(self):
        """ Verify errors thrown when payment amount is greater
        than order amount and a refund is required from Support """
        payment = PaymentEventFactory(order=self.order,
                                      amount=100,
                                      event_type_id=self.payevent.id,
                                      date_created=self.timestamp)
        payment.save()
        with self.assertRaises(CommandError) as cm:
            call_command('verify_transactions', '--support')
        exception = str(cm.exception)
        self.assertTrue(payment.amount != self.order.total_incl_tax)
        self.assertIn("There was a mismatch in the totals in the following order that require a refund", exception)
        self.assertIn("orders_mismatched_totals_support", exception)
        self.assertIn(str(self.order.id), exception)
        self.assertIn(str(payment.id), exception)
        self.assertIn('"order_amount": 90.0', exception)
        self.assertIn('"payment_amount": 100.0', exception)
        self.assertIn('"refund_amount": 10.0', exception)

    def test_refund_exceeded(self):
        """ Test verify_transactions with refund which exceed amount paid """
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
        exception = str(cm.exception)
        self.assertIn("The following orders had excessive refunds", exception)
        self.assertIn(str(self.order.id), exception)
        self.assertIn(str(refund.id), exception)
        self.assertIn('"amount": 90.0', exception)
        self.assertIn('"amount": 100.0', exception)
