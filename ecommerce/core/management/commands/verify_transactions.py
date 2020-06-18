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
import json
import logging

import pytz
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum
from oscar.core.loading import get_class, get_model

from ecommerce.core.constants import COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME, SEAT_PRODUCT_CLASS_NAME
from ecommerce.core.utils import use_read_replica_if_available

logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
PaymentEvent = get_model('order', 'PaymentEvent')
PaymentEventType = get_model('order', 'PaymentEventType')
PaymentEventTypeName = get_class('order.constants', 'PaymentEventTypeName')

DEFAULT_START_DELTA_TIME = 240
DEFAULT_END_DELTA_TIME = 60
VALID_PRODUCT_CLASS_NAMES = [SEAT_PRODUCT_CLASS_NAME, COURSE_ENTITLEMENT_PRODUCT_CLASS_NAME]


class Command(BaseCommand):
    ERRORS_DICT = None
    PAID_EVENT_TYPE = None
    REFUNDED_EVENT_TYPE = None

    help = 'Management command to verify ecommerce transactions and log if there is any imbalance.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-delta',
            action='store',
            type=int,
            default=DEFAULT_START_DELTA_TIME,
            help='Minutes before now to start looking at orders.'
        )
        parser.add_argument(
            '--end-delta',
            action='store',
            type=int,
            default=DEFAULT_END_DELTA_TIME,
            help='Minutes before now to end looking at orders.'
        )
        parser.add_argument(
            '--threshold',
            metavar='N',
            action='store',
            type=float,
            default=0,
            help='Anomoly threshold to trigger failure.  If N is between 0 and 1, this will be the fraction of total '
                 'orders; N >= 1 will be an integer number of errors')
        parser.add_argument(
            '--support',
            action='store_true',
            help='Mismatched orders to go to Support'
        )

    def handle(self, *args, **options):
        logger.info("Verify transactions with options: %r", options)

        self.ERRORS_DICT = {}
        self.PAID_EVENT_TYPE = PaymentEventType.objects.get(name=PaymentEventTypeName.PAID)
        self.REFUNDED_EVENT_TYPE = PaymentEventType.objects.get(name=PaymentEventTypeName.REFUNDED)

        support = options['support']
        start_delta = options['start_delta']
        end_delta = options['end_delta']
        threshold = max(options['threshold'], 0)

        start = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=start_delta)
        end = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=end_delta)
        logger.info("Start time: %s  --  End time: %s", start, end)

        orders = use_read_replica_if_available(Order.objects.all()
                                               .filter(date_placed__gte=start, date_placed__lt=end)
                                               .prefetch_related('payment_events__event_type'))
        logger.info("Number of orders to verify: %s", orders.count())
        if orders.count() == 0:
            logger.info("No orders, DONE")
            return

        if support:
            self.handle_support(orders)
        else:
            self.handle_alert(orders, threshold)

    def process_errors(self, orders):
        # FIXME: it is possible for an order to have more than one error, so this really should
        # count "unique orders with errors", not number of errors
        error_count = sum([len(v["errors"]) for v in self.ERRORS_DICT.values()])
        exit_errors = json.dumps(self.ERRORS_DICT)
        error_rate = float(error_count) / orders.count()

        logger.info("Summary: %d errors, %.1f %%", error_count, error_rate * 100.0)

        return error_count, exit_errors, error_rate

    def handle_alert(self, orders, threshold):
        for order in orders:
            self.validate_order(order)

        error_count, exit_errors, error_rate = self.process_errors(orders)

        if threshold == 0 or threshold >= 1:
            threshold = int(threshold)
            flunk = error_count > threshold
        else:
            flunk = error_rate > threshold

        if flunk:
            raise CommandError("Errors in transactions: {errors}".format(errors=exit_errors))
        if self.ERRORS_DICT:
            logger.warning("Errors in transactions within threshold (%r): %s", threshold, exit_errors)

    def handle_support(self, orders):
        for order in orders:
            all_payment_events = order.payment_events
            payments = all_payment_events.filter(event_type=self.PAID_EVENT_TYPE)

            # If the payment total and the order total do not match, flag for review.
            if payments.count() == 1 and payments[0].amount != order.total_incl_tax:
                mismatch_total = float(payments[0].amount - order.total_incl_tax)
                # FIXME: validate_order should be changed to log _all_ errors related to an order
                # If payment amount > order amount, a refund is required from Support
                if mismatch_total > 0:
                    error_dict = {
                        "order_number": order.number,
                        "order_id": order.id,
                        "order_amount": float(order.total_incl_tax),
                        # Assuming just one payment since we do not support multi-payment
                        "payment_id": payments[0].id,
                        "payment_amount": float(payments[0].amount),
                        "user_email": order.guest_email,
                        "refund_amount": mismatch_total
                    }
                    self.add_error(
                        "orders_mismatched_totals_support",
                        "There was a mismatch in the totals in the following order that require a refund",
                        error_dict=error_dict,
                    )

        error_count, exit_errors, error_rate = self.process_errors(orders)
        if error_count and error_rate > 0:
            raise CommandError("Errors in transactions: {errors}".format(errors=exit_errors))

    def validate_order(self, order):
        all_payment_events = order.payment_events
        refunds = all_payment_events.filter(event_type=self.REFUNDED_EVENT_TYPE)
        payments = all_payment_events.filter(event_type=self.PAID_EVENT_TYPE)

        # If a coupon is used to purchase a product for the full price, there will be no PaymentEvent
        # so we must also verify that order had a price > 0.
        if payments.count() == 0:
            if self.order_requires_payment(order) and order.total_incl_tax > 0:
                self.add_error(
                    "orders_no_payment",
                    "The following orders are without payments",
                    order
                )

        # We do not support multi-payment today, so flag this for review.
        elif payments.count() > 1:
            self.add_error(
                "orders_multi_payment",
                "The following orders had multiple payments",
                order,
                payments
            )

        # If the payment total and the order total do not match, flag for review.
        elif payments.aggregate(total=Sum('amount')).get('total') != order.total_incl_tax:
            # FIXME: validate_order should be changed to log _all_ errors related to an order
            self.add_error(
                "orders_mismatched_totals",
                "The following order totals mismatch payments received",
                order,
                payments
            )

        refund_total = refunds.aggregate(total=Sum('amount')).get('total')
        payment_total = payments.aggregate(total=Sum('amount')).get('total')
        if refund_total is not None and refund_total > payment_total:
            self.add_error(
                "orders_refund_exceeded",
                "The following orders had excessive refunds",
                order,
                refunds
            )

    def add_error(self, tag, msg, order=None, payments=None, error_dict=None):
        if tag not in self.ERRORS_DICT:
            self.ERRORS_DICT[tag] = {"message": msg, "errors": []}
        if error_dict:
            self.ERRORS_DICT[tag]["errors"].append(error_dict)
        else:
            self.ERRORS_DICT[tag]["errors"].append(self.create_error_dict(order, payments))

    def create_error_dict(self, order, payments=None):
        d = {}
        d["order"] = {
            "order_id": order.id,
            "order_number": order.number,
            "amount": float(order.total_incl_tax),
        }
        if payments:
            d["payments"] = [
                {
                    "payment_id": p.id,
                    "processor": p.processor_name,
                    "amount": float(p.amount),
                    "type": p.event_type.name,
                }
                for p in payments
            ]
        return d

    def order_requires_payment(self, order):
        # We only expect immediate payments for Seats and Entitlements.
        # Filter out orders that were flagged as being without payment for other product types
        # FIXME: there are better ways to do this
        for line in order.lines.all():
            name = line.product.get_product_class().name
            if name in VALID_PRODUCT_CLASS_NAMES:
                return True
        return False
