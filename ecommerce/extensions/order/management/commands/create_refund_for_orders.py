"""
This command generates refunds for orders.
./manage.py create_refund_for_orders --order-numbers-file=order_numbers_file.txt
./manage.py create_refund_for_orders --order-numbers-file=order_numbers_file.txt --refund-duplicate-only
./manage.py create_refund_for_orders --order-numbers-file=order_numbers_file.txt --refund-duplicate-only  --no-commit
./manage.py create_refund_for_orders --order-numbers-file=order_numbers_file.txt --refund-duplicate-only  --sleep-time=1
"""


import logging
import os
import time

from django.core.management import BaseCommand, CommandError
from django.db.utils import IntegrityError
from oscar.core.loading import get_model
from requests import Timeout
from slumber.exceptions import HttpServerError, SlumberBaseException

from ecommerce.extensions.fulfillment.status import LINE

logger = logging.getLogger(__name__)

Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
Product = get_model('catalogue', 'Product')
Refund = get_model('refund', 'Refund')


class RefundError(Exception):
    """
    Raised when refund could not be processed.
    """


class Command(BaseCommand):
    """
    Creates refund for orders.
    """

    help = 'Create refund for orders.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--order-numbers-file',
            action='store',
            dest='order_numbers_file',
            default=None,
            help='Path of the file to read order numbers from.',
            type=str,
        )
        parser.add_argument(
            '--refund-duplicate-only',
            action='store_true',
            dest='refund_duplicate_only',
            default=False,
            help='Refund duplicate orders bought by the user with multiple enrollment mode (except audit).',
        )
        parser.add_argument(
            '--no-commit',
            action='store_true',
            dest='no_commit',
            default=False,
            help='Dry Run, print log messages without committing anything.',
        )
        parser.add_argument(
            '--sleep-time',
            action='store',
            dest='sleep_time',
            type=float,
            default=0.0,
            help='Sleep time in seconds after executing each order from file.'
        )

    def handle(self, *args, **options):
        order_numbers_file = options[str('order_numbers_file')]
        remove_duplicate_only = options['refund_duplicate_only']
        should_commit = not options['no_commit']
        sleep_time = options['sleep_time']

        if not order_numbers_file or not os.path.exists(order_numbers_file):
            raise CommandError(
                'Pass the correct absolute path to order numbers file as --order-numbers-file argument.'
            )
        total_orders, failed_orders, skipped_orders, success_orders = self._create_refunds_from_file(
            order_numbers_file,
            remove_duplicate_only,
            should_commit,
            sleep_time,
        )
        logger.info(u'[Ecommerce Order Refund] Success Orders: %s', success_orders)
        if failed_orders or skipped_orders:
            logger.error(
                u'[Ecommerce Order Refund]: Completed refund generation. %d of %d failed and %d skipped.\n'
                u'Failed orders: %s\n'
                u'Skipped orders: %s\n',
                len(failed_orders),
                total_orders,
                len(skipped_orders),
                '\n'.join(failed_orders),
                '\n'.join(skipped_orders),
            )
        else:
            logger.info(u'[Ecommerce Order Refund] Generated refunds for the batch of %d orders.', total_orders)

    def _already_enrolled_in_another_seat_of_same_course(self, product_seat, user):
        """
        Check if the user was also enrolled in a another seat of the same course (having different course_mode).
        :return: True if enrolled
        """
        course = product_seat.course

        seat_products = course.seat_products.filter(
            attributes__name='certificate_type'
        ).exclude(
            attribute_values__value_text='audit'
        ).exclude(
            pk=product_seat.pk   # removing current manual order product seat
        )

        # check if an order already exists
        order_line = OrderLine.objects.filter(product__in=seat_products, order__user=user, status=LINE.COMPLETE)
        return order_line.exists()

    def _create_refunds_from_file(self, order_numbers_file, refund_duplicate_only, should_commit, sleep_time):
        """
        Generate refunds for the orders provided in the order numbers file.

        Arguments:
            order_numbers_file (str): path of the file containing order numbers.

        Returns:
            (total_orders, failed_orders): a tuple containing count of orders processed and a list containing
            order numbers whose refunds could not be generated.
        """
        failed_orders = []
        skipped_orders = []
        success_orders = []

        with open(order_numbers_file, 'r') as file_handler:
            order_numbers = file_handler.readlines()
            total_orders = len(order_numbers)
            logger.info(u'Creating refund for %d orders.', total_orders)
            for index, order_number in enumerate(order_numbers, start=1):
                try:
                    order_number = order_number.strip()
                    order = Order.objects.get(number=order_number)

                    if refund_duplicate_only:
                        seat_product = order.lines.first().product
                        if not self._already_enrolled_in_another_seat_of_same_course(seat_product, order.user):
                            skipped_orders.append(order_number)
                            continue

                    if should_commit:
                        refund = Refund.create_with_lines(order, list(order.lines.all()))
                        if refund is None:
                            raise RefundError
                    success_orders.append(order_number)
                except (Order.DoesNotExist, RefundError, IntegrityError, SlumberBaseException, ConnectionError,
                        Timeout, HttpServerError) as e:
                    failed_orders.append(order_number)
                    logger.exception(
                        u'[Ecommerce Order Refund] %d/%d '
                        u'Failed to generate refund for %s. %s', index, total_orders, order_number, str(e)
                    )
                if sleep_time:
                    logger.info(u'Sleeping for %s second/seconds', sleep_time)
                    time.sleep(sleep_time)
        return total_orders, failed_orders, skipped_orders, success_orders
