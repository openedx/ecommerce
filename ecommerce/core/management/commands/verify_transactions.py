"""
Django management command to verify ecommerce transactions.

Command is run by Jenkins job each hour. By default the job runs on a three
hour time window starting one hour in the past.

For each order in the time window the command verifies exactly one payment of
the expected value exists in the database.

If a PaymentEvent does not exist, multiple PaymentEvents exist, or the
PaymentEvent amount is different from the order amount, then the order
id and relevant payment information is logged in a list associated with
each of these scenarios.

After considering each order in the time window the errors are input into the
exit_errors dictionary. If any errors exist at the end of the script a
CommandError is raised and the dictionary is printed as a string log.

Example output:
    CommandError:
    Errors in transactions: {'orders_no_pay':
    'The following orders are without payments [73L, 60L, 29L]. ',
    'multi_pay_on_order': 'The following orders had multiple payments
    [(72L, [67L, 66L])]',
    'totals_mismatch': "Order totals mismatch with payments received.
    [('Order: 72 Amount: 100.00', 'Payment: 67 Amount: 10000.00'),
    ('Order: 71 Amount: 100.00', 'Payment: 65 Amount: 10.00')]"}
"""

import datetime
import logging

import pytz
from django.core.management.base import BaseCommand, CommandError
from oscar.core.loading import get_model

logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')

DEFAULT_START_DELTA_TIME = 240
DEFAULT_END_DELTA_TIME = 60


class Command(BaseCommand):

    help = 'Management command to verify ecommerce transactions and log if there is any imbalance.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-delta',
            action='store',
            dest='start_delta',
            type=int,
            default=DEFAULT_START_DELTA_TIME,
            help='Minutes before now to start looking at orders.'
        )
        parser.add_argument(
            '--end-delta',
            action='store',
            dest='end_delta',
            type=int,
            default=DEFAULT_END_DELTA_TIME,
            help='Minutes before now to end looking at orders.'
        )

    def handle(self, *args, **options):
        start_delta = options['start_delta']
        end_delta = options['end_delta']
        exit_errors = {}
        start = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=start_delta)
        end = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=end_delta)

        orders = Order.objects.all().filter(date_placed__gte=start, date_placed__lt=end)

        orders_without_payments = []
        multi_payment_on_order = []
        order_payment_totals_mismatch = []

        for order in orders:
            payment_events = PaymentEvent.objects.filter(order_id=order.id)
            if payment_events.count() == 0 and order.total_incl_tax > 0:
                # If a coupon is used to purchase a product for the full price, there will be no PaymentEvent.
                orders_without_payments.append(order.id)
            if payment_events.count() > 1:
                if payment_events.count() == 2:
                    event1 = payment_events[0]
                    event2 = payment_events[1]
                    if event1.event_type_id == event2.event_type_id:
                        # If PaymentEvents are the same type then there were multiple payments.
                        multi_payment_on_order.append((order.id, [event.id for event in payment_events]))
                else:
                    multi_payment_on_order.append((order.id, [event.id for event in payment_events]))
            for event in payment_events:
                print("event: ", event)
                if event.amount != order.total_incl_tax:
                    order_payment_totals_mismatch.append(("Order: " + str(order.id) + " Amount: " +
                                                          str(order.total_incl_tax), "Payment: " +
                                                          str(event.id) + " Amount: " +
                                                          str(event.amount)))

        if order_payment_totals_mismatch:
            exit_errors["totals_mismatch"] = "Order totals mismatch with payments received. " \
                                             + str(order_payment_totals_mismatch)
        if orders_without_payments:
            exit_errors["orders_no_pay"] = "The following orders are without payments " \
                                           + str(orders_without_payments) + ". "
        if multi_payment_on_order:
            exit_errors["multi_pay_on_order"] = "The following orders had multiple payments " \
                                                + str(multi_payment_on_order)
        if exit_errors:
            print("exit errors: ", exit_errors)
            raise CommandError("Errors in transactions: " + str(exit_errors))
