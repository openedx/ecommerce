"""
This command generates refunds for orders.
"""
from __future__ import absolute_import, unicode_literals

import logging
import os

from django.core.management import BaseCommand, CommandError
from django.db.utils import IntegrityError
from oscar.core.loading import get_model

logger = logging.getLogger(__name__)

Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
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

    def handle(self, *args, **options):
        order_numbers_file = options[str('order_numbers_file')]
        total_orders, failed_orders = 0, None
        if order_numbers_file:
            if not os.path.exists(order_numbers_file):
                raise CommandError(
                    'Pass the correct absolute path to order numbers file as --order-numbers-file argument.'
                )
            total_orders, failed_orders = self._create_refunds_from_file(order_numbers_file)
        if failed_orders:
            logger.error(
                u'[Ecommerce Order Refund]: Completed refund generation. %d of %d failed. '
                u'Failed orders: \n%s', len(failed_orders), total_orders, '\n'.join(failed_orders))
        else:
            logger.info(u'[Ecommerce Order Refund] Generated refunds for the batch of %d orders.', total_orders)

    def _create_refunds_from_file(self, order_numbers_file):
        """
        Generate refunds for the orders provided in the order numbers file.

        Arguments:
            order_numbers_file (str): path of the file containing order numbers.

        Returns:
            (total_orders, failed_orders): a tuple containing count of orders processed and a list containing
            order numbers whose refunds could not be generated.
        """
        failed_orders = []

        with open(order_numbers_file, 'r') as file_handler:
            order_numbers = file_handler.readlines()
            total_orders = len(order_numbers)
            logger.info(u'Creating refund for %d orders.', total_orders)
            for index, order_number in enumerate(order_numbers, start=1):
                try:
                    order_number = order_number.strip()
                    order = Order.objects.get(number=order_number)
                    refund = Refund.create_with_lines(order, list(order.lines.all()))
                    if refund is None:
                        raise RefundError
                except (Order.DoesNotExist, RefundError, IntegrityError) as e:
                    failed_orders.append(order_number)
                    logger.error(
                        u'[Ecommerce Order Refund] %d/%d '
                        u'Failed to generate refund for %s. %s', index, total_orders, order_number, str(e))
        return total_orders, failed_orders
