from __future__ import unicode_literals

import logging

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

    def handle(self, *args, **options):
        cutoff_date = options['cutoff_date']
        batch_size = options['batch_size']

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
            qs = model.history.filter(history_date__lte=cutoff_date)

            message = 'Cleaning {} rows from {} table'.format(qs.count(), model.__name__)
            logger.info(message)

            qs = qs[:batch_size]
            while qs.exists():
                history_batch = qs.values_list('id', flat=True)
                with transaction.atomic():
                    model.history.filter(pk__in=list(history_batch)).delete()

                qs = model.history.filter(history_date__lte=cutoff_date)[:batch_size]
