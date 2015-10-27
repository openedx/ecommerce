"""
Management command that deletes baskets associated with orders.

These baskets don't have much value once the order is placed, and unnecessarily take up space.
"""
from __future__ import unicode_literals
from django.core.management import BaseCommand
from django.db import transaction
from oscar.core.loading import get_model

Basket = get_model('basket', 'Basket')


class Command(BaseCommand):
    help = 'Delete baskets for which orders have been placed.'

    def add_arguments(self, parser):
        parser.add_argument('-b', '--batch-size',
                            action='store',
                            dest='batch_size',
                            default=1000,
                            type=int,
                            help='Size of each batch of baskets to be deleted.')
        parser.add_argument('--commit',
                            action='store_true',
                            dest='commit',
                            default=False,
                            help='Actually delete the baskets.')

    def handle(self, *args, **options):
        queryset = Basket.objects.filter(order__isnull=False)
        count = queryset.count()

        if options['commit']:
            if count:
                self.stderr.write('Deleting [{}] baskets...'.format(count))
                batch_size = options['batch_size']
                max_id = queryset.order_by('-id')[0].id
                for start in range(0, max_id, batch_size):
                    end = min(start + batch_size, max_id)
                    self.stderr.write('...deleting baskets [{start}] through [{end}]...'.format(start=start, end=end))
                    with transaction.atomic():
                        queryset.filter(pk__gte=start, pk__lte=end).delete()

                self.stderr.write('Done.')
            else:
                self.stderr.write('No baskets to delete.')
        else:
            msg = 'This has been an example operation. If the --commit flag had been included, the command ' \
                  'would have deleted [{}] baskets.'.format(count)
            self.stderr.write(msg)
