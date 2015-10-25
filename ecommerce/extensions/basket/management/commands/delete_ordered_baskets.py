"""
Management command that deletes baskets associated with orders.

These baskets don't have much value once the order is placed, and unnecessarily take up space.
"""
from __future__ import unicode_literals
from django.core.management import BaseCommand
from oscar.core.loading import get_model

Basket = get_model('basket', 'Basket')


class Command(BaseCommand):
    help = 'Delete baskets for which orders have been placed.'

    def add_arguments(self, parser):
        parser.add_argument('--commit',
                            action='store_true',
                            dest='commit',
                            default=False,
                            help='Actually delete the baskets.')

    def handle(self, *args, **options):
        queryset = Basket.objects.filter(order__isnull=False)
        count = queryset.count()

        if options['commit']:
            self.stderr.write('Deleting [{}] baskets...'.format(count))
            queryset.delete()
            self.stderr.write('Done.')
        else:
            msg = 'This is a dry run. Had the --commit flag been included, [{}] baskets would have been deleted.'. \
                format(count)
            self.stderr.write(msg)
