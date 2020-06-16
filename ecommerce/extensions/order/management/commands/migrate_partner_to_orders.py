

import logging
import time
from textwrap import dedent

from django.core.management.base import BaseCommand
from django.db import transaction
from oscar.core.loading import get_model

logger = logging.getLogger(__name__)
Order = get_model('order', 'Order')
SiteConfiguration = get_model('core', 'SiteConfiguration')


class Command(BaseCommand):
    """
    Command to add partner to orders.

    Example:

        ./manage.py migrate_partner_to_orders
    """
    help = dedent(__doc__)

    def add_arguments(self, parser):
        parser.add_argument('--batch_size',
                            action='store',
                            dest='batch_size',
                            type=int,
                            default=1000,
                            help='Maximum number of database rows to update per query. '
                                 'This helps avoid locking the database while updating large amount of data.')
        parser.add_argument('--sleep_time',
                            action='store',
                            dest='sleep_time',
                            type=int,
                            default=10,
                            help='Sleep time in seconds between update of batches')

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        sleep_time = options['sleep_time']

        for site_configuration in SiteConfiguration.objects.all():
            partner = site_configuration.partner
            site = site_configuration.site

            orders = Order.objects.filter(site=site).exclude(partner=partner).order_by('-pk')

            message = 'Adding partner [{}] in {} orders for site [{}]'.format(
                partner.short_code, orders.count(), site.domain
            )
            logger.info(message)

            try:
                # use primary keys sorting to make sure unique batching as
                # filtering batch does not work for huge data
                max_pk = orders[0].pk
                batch_start = orders.reverse()[0].pk
                batch_stop = batch_start + batch_size
            except IndexError:
                continue

            while batch_start <= max_pk:
                batch_queryset = orders.filter(pk__gte=batch_start, pk__lt=batch_stop)
                count = batch_queryset.count()

                with transaction.atomic():
                    batch_queryset.update(partner=partner)
                    logger.info(
                        'Partner [%s] successfully added in %d orders with PKs between %d and %d for site [%s]',
                        partner.short_code, count, batch_start, batch_stop, site.domain
                    )

                if batch_stop < max_pk:
                    time.sleep(sleep_time)

                batch_start = batch_stop
                batch_stop += batch_size
