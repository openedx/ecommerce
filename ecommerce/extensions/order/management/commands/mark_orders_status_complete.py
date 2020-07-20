"""
This command mark orders with status Fulfillment Error as completed.
"""


import logging
import os
import time
from textwrap import dedent

from django.core.management import BaseCommand, CommandError
from oscar.core.loading import get_model

from ecommerce.extensions.fulfillment.status import LINE, ORDER

logger = logging.getLogger(__name__)

MarkOrdersStatusCompleteConfig = get_model('order', 'MarkOrdersStatusCompleteConfig')
Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
Product = get_model('catalogue', 'Product')


class Command(BaseCommand):
    """
    Mark orders with status Fulfillment Error as completed.

    Example:
        ./manage.py mark_orders_status_complete --order-numbers-file=order_numbers_file.txt
        ./manage.py mark_orders_status_complete --order-numbers-file=order_numbers_file.txt  --no-commit
        ./manage.py mark_orders_status_complete --order-numbers-file=order_numbers_file.txt  --sleep-time=1
    """

    help = dedent(__doc__)

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
            '--file-from-database',
            action='store_true',
            help='Use file from the MarkOrdersStatusCompleteConfig model instead of the command line.',
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
            type=int,
            default=0,
            help='Sleep time in seconds after executing each order from file.'
        )

    def get_file_from_database(self):
        """ Get file from the current MarkOrdersStatusCompleteConfig model. """
        config = MarkOrdersStatusCompleteConfig.current()
        if not config.enabled:
            raise CommandError('MarkOrdersStatusCompleteConfig is disabled, but --file-from-database was requested.')

        return config.txt_file

    def handle(self, *args, **options):
        should_commit = not options['no_commit']
        sleep_time = options['sleep_time']
        if options['file_from_database']:
            order_numbers_file = self.get_file_from_database()
        else:
            order_numbers_file = options[str('order_numbers_file')]
            if not order_numbers_file or not os.path.exists(order_numbers_file):
                raise CommandError(
                    'Pass the correct absolute path to order numbers file as --order-numbers-file argument.'
                )

            order_numbers_file = open(order_numbers_file, 'rb')

        order_numbers = order_numbers_file.readlines()
        total_orders, failed_orders, skipped_orders = self._mark_orders_status_complete_from_file(
            order_numbers,
            should_commit,
            sleep_time,
        )

        order_numbers_file.close()

        logger.info(
            u'[Mark Orders Status Complete] Execution of command mark orders status complete is successful.\n'
            u'Total orders received: %d\n'
            u'Orders marked as completed: %d\n'
            u'Failed orders: %s\n'
            u'Skipped orders: %s\n',
            total_orders,
            total_orders - (len(failed_orders) + len(skipped_orders)),
            ', '.join(failed_orders),
            ', '.join(skipped_orders),
        )

    def _mark_orders_status_complete_from_file(self, order_numbers, should_commit, sleep_time):
        """
        Mark orders status complete for the orders provided in the order numbers file.

        Arguments:
            order_numbers (list): List containing order numbers
            should_commit (bool): If true commit changes into database
            sleep_time (int): Sleep time in seconds after executing each order

        Returns:
            (total_orders, failed_orders, skipped_orders): a tuple containing count of orders
            processed and two lists of failed and skipped order numbers.
        """
        failed_orders = []
        skipped_orders = []

        total_orders = len(order_numbers)
        logger.info(
            u'[Mark Orders Status Complete] '
            u'Starting mark order status as complete process for %d orders.', total_orders
        )
        for index, order_number in enumerate(order_numbers, start=1):
            try:
                order_number = order_number.decode('utf-8').strip()
                order = Order.objects.get(number=order_number)

                if order.status != ORDER.FULFILLMENT_ERROR:
                    skipped_orders.append(order_number)
                    continue

                if should_commit:
                    self._change_order_status_to_complete(order)

            except Exception as e:  # pylint: disable=broad-except
                failed_orders.append(order_number)
                logger.exception(
                    u'[Mark Orders Status Complete] %d/%d '
                    u'Failed to change status for order %s. %s', index, total_orders, order_number, str(e)
                )

            if sleep_time:
                logger.info(
                    u'[Mark Orders Status Complete] '
                    u'Sleeping for %s seconds', sleep_time
                )
                time.sleep(sleep_time)

        return total_orders, failed_orders, skipped_orders

    def _change_order_status_to_complete(self, order):
        """
        Change order and order.lines status to complete.
        """
        for line in order.lines.all():
            line.set_status(LINE.COMPLETE)

        order.set_status(ORDER.COMPLETE)
