"""
Management command that deletes baskets associated with orders.

These baskets don't have much value once the order is placed, and unnecessarily take up space.
"""


import time

from django.core.management import BaseCommand
from django.db import transaction
from oscar.core.loading import get_model

Basket = get_model('basket', 'Basket')


class Command(BaseCommand):
    help = 'Delete baskets for which orders have been placed.'

    def add_arguments(self, parser):
        # Batched deletion prevents the entire table from locking up as the command executes.
        parser.add_argument('-b', '--batch-size',
                            action='store',
                            dest='batch_size',
                            default=1000,
                            type=int,
                            help='Size of each batch of baskets to be deleted.')
        # Sleeping between each batch deletion gives MySQL time to process other connections.
        parser.add_argument('-s', '--sleep-seconds',
                            action='store',
                            dest='sleep_seconds',
                            default=3,
                            type=int,
                            help='Seconds to sleep between each batch deletion.')
        parser.add_argument('--commit',
                            action='store_true',
                            dest='commit',
                            default=False,
                            help='Actually delete the baskets.')

    def handle(self, *args, **options):
        # Only select those baskets linked to an order, and those not linked to an invoice.
        # TODO: Simplify this query when the foreign key to Basket is removed from Invoice.
        queryset = Basket.objects.filter(order__isnull=False, invoice__isnull=True)
        count = queryset.count()

        if options['commit']:
            if count:
                self.stderr.write('Deleting [{}] baskets.'.format(count))

                batch_size = options['batch_size']
                sleep_seconds = options['sleep_seconds']

                max_id = queryset.order_by('-id')[0].id
                for start in range(0, max_id, batch_size):
                    end = min(start + batch_size, max_id)
                    self.stderr.write('Deleting baskets [{start}] through [{end}].'.format(start=start, end=end))
                    with transaction.atomic():
                        queryset.filter(pk__gte=start, pk__lte=end).delete()

                    self.stderr.write('Complete. Sleeping.'.format(start=start, end=end))
                    time.sleep(sleep_seconds)

                self.stderr.write('All baskets deleted.')
            else:
                self.stderr.write('No baskets to delete.')
        else:
            msg = 'This has been an example operation. If the --commit flag had been included, the command ' \
                  'would have deleted [{}] baskets.'.format(count)
            self.stderr.write(msg)
