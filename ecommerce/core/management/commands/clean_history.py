from __future__ import unicode_literals

import logging
import time

from dateutil.parser import parse
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from oscar.core.loading import get_model

from ecommerce.courses.models import Course
from ecommerce.invoice.models import Invoice

logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
OrderLine = get_model('order', 'Line')
Product = get_model('catalogue', 'Product')
ProductAttributeValue = get_model('catalogue', 'ProductAttributeValue')
Refund = get_model('refund', 'Refund')
RefundLine = get_model('refund', 'RefundLine')
StockRecord = get_model('partner', 'StockRecord')


class Command(BaseCommand):
    help = 'Clean history data'

    def add_arguments(self, parser):
        parser.add_argument('--cutoff_date',
                            action='store',
                            dest='cutoff_date',
                            type=str,
                            required=True,
                            help='Cutoff date before which the history data should be cleaned. '
                                 'format is YYYY-MM-DD')
        parser.add_argument('--batch_size',
                            action='store',
                            dest='batch_size',
                            type=int,
                            default=1000,
                            help='Maximum number of database rows to delete per query. '
                                 'This helps avoid locking the database when deleting large amounts of data.')
        parser.add_argument('--sleep_time',
                            action='store',
                            dest='sleep_time',
                            type=int,
                            default=10,
                            help='Sleep time between deletion of batches')

    def handle(self, *args, **options):
        cutoff_date = options['cutoff_date']
        batch_size = options['batch_size']
        sleep_time = options['sleep_time']

        try:
            cutoff_date = parse(cutoff_date)
        except:  # pylint: disable=bare-except
            msg = 'Failed to parse cutoff date: {}'.format(cutoff_date)
            logger.exception(msg)
            raise CommandError(msg)

        models = (
            Order, OrderLine, Refund, RefundLine, ProductAttributeValue, Product, StockRecord, Course, Invoice,
        )

        for model in models:
            qs = model.history.filter(history_date__lte=cutoff_date).order_by('-pk')

            message = 'Cleaning {} rows from {} table'.format(qs.count(), model.__name__)
            logger.info(message)

            try:
                # use Primary keys sorting to make sure unique batching as
                # filtering batch does not work for huge data
                max_pk = qs[0].pk
                batch_start = qs.reverse()[0].pk
                batch_stop = batch_start + batch_size
            except IndexError:
                continue

            logger.info(message)

            while batch_start <= max_pk:
                queryset = model.history.filter(pk__gte=batch_start, pk__lt=batch_stop)

                with transaction.atomic():
                    queryset.delete()
                    logger.info(
                        'Deleted instances of %s with PKs between %d and %d',
                        model.__name__, batch_start, batch_stop
                    )

                if batch_stop < max_pk:
                    time.sleep(sleep_time)

                batch_start = batch_stop
                batch_stop += batch_size
