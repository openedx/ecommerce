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
    ORDERS_WITHOUT_PAYMENTS = None
    MULTI_PAYMENT_ON_ORDER = None
    ORDER_PAYMENT_TOTALS_MISMATCH = None
    REFUND_AMOUNT_EXCEEDED = None
    PAID_EVENT_TYPE = None
    REFUNDED_EVENT_TYPE = None

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
        self.ORDERS_WITHOUT_PAYMENTS = []
        self.MULTI_PAYMENT_ON_ORDER = []
        self.ORDER_PAYMENT_TOTALS_MISMATCH = []
        self.REFUND_AMOUNT_EXCEEDED = []
        self.PAID_EVENT_TYPE = PaymentEventType.objects.get(name=PaymentEventTypeName.PAID)
        self.REFUNDED_EVENT_TYPE = PaymentEventType.objects.get(name=PaymentEventTypeName.REFUNDED)

        start_delta = options['start_delta']
        end_delta = options['end_delta']

        start = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=start_delta)
        end = datetime.datetime.now(pytz.utc) - datetime.timedelta(minutes=end_delta)

        orders = use_read_replica_if_available(
            Order.objects.all()
            .filter(date_placed__gte=start, date_placed__lt=end)
            .prefetch_related('payment_events__event_type')
        )

        logger.info("Number of orders to verify: %s", orders.count())

        for order in orders:
            all_payment_events = order.payment_events
            refunds = all_payment_events.filter(event_type=self.REFUNDED_EVENT_TYPE)
            payments = all_payment_events.filter(event_type=self.PAID_EVENT_TYPE)

            self.validate_order_payments(order, payments)
            self.validate_order_refunds(order, refunds, payments)

        self.clean_orders()
        exit_errors = self.compile_errors()

        if exit_errors:
            raise CommandError("Errors in transactions: {errors}".format(errors=exit_errors))

    def validate_order_payments(self, order, payments):
        # If a coupon is used to purchase a product for the full price, there will be no PaymentEvent
        # so we must also verify that order had a price > 0.
        if payments.count() == 0:
            if order.total_incl_tax > 0:
                self.ORDERS_WITHOUT_PAYMENTS.append(
                    (order, None)
                )
            return

        # We do not support multi-payment today, so flag this for review.
        if payments.count() > 1:
            self.MULTI_PAYMENT_ON_ORDER.append(
                (order, payments)
            )

        # If the payment total and the order total do not match, flag for review.
        if payments.aggregate(total=Sum('amount')).get('total') != order.total_incl_tax:
            self.ORDER_PAYMENT_TOTALS_MISMATCH.append(
                (order, payments)
            )

    def validate_order_refunds(self, order, refunds, payments):
        refund_total = refunds.aggregate(total=Sum('amount')).get('total')
        payment_total = payments.aggregate(total=Sum('amount')).get('total')
        if refund_total > payment_total:
            self.REFUND_AMOUNT_EXCEEDED.append(
                (order, refunds)
            )

    def compile_errors(self):
        exit_errors = {}
        if self.ORDER_PAYMENT_TOTALS_MISMATCH:
            exit_errors["totals_mismatch"] = "Order totals mismatch with payments received. " \
                                             + self.error_msg(self.ORDER_PAYMENT_TOTALS_MISMATCH)
        if self.ORDERS_WITHOUT_PAYMENTS:
            exit_errors["orders_no_pay"] = "The following orders are without payments " \
                                           + self.error_msg(self.ORDERS_WITHOUT_PAYMENTS)
        if self.MULTI_PAYMENT_ON_ORDER:
            exit_errors["multi_pay_on_order"] = "The following orders had multiple payments " \
                                                + self.error_msg(self.MULTI_PAYMENT_ON_ORDER)

        if self.REFUND_AMOUNT_EXCEEDED:
            exit_errors["refund_amount_exceeded"] = "The following orders had excessive refunds " \
                                                    + self.error_msg(self.REFUND_AMOUNT_EXCEEDED)
        return exit_errors

    def error_msg(self, errors):
        msg = ""
        for order, payments in errors:
            order_str = "Order(Id: {order_id}, Number: {num}, Amount: {amount}) \n".format(
                order_id=order.id,
                num=order.number,
                amount=order.total_incl_tax
            )
            payment_str = ""

            if payments:
                for payment in payments:
                    payment_str += "Payment(Id: {payment_id}, Processor: {processor}, " \
                        "Amount: {amount}, Type:{type} \n" \
                        .format(
                            payment_id=payment.id,
                            processor=payment.processor_name,
                            amount=payment.amount,
                            type=payment.event_type.name
                        )
            msg += order_str
            msg += payment_str
        return msg

    def clean_orders(self):
        # We only expect immediate payments for Seats and Entitlements.
        # Filter out orders that were flagged as being without payment for other product types
        cleaned_orders_without_payments = [
            (o, p) for o, p in self.ORDERS_WITHOUT_PAYMENTS if self.valid_order_without_payment(o)
        ]
        self.ORDERS_WITHOUT_PAYMENTS = cleaned_orders_without_payments

    def valid_order_without_payment(self, order):
        valid = False
        for line in order.lines.all():
            if self.verifiable_product(line.product):
                valid = True

        return valid

    def verifiable_product(self, product):
        return product.get_product_class().name in VALID_PRODUCT_CLASS_NAMES
