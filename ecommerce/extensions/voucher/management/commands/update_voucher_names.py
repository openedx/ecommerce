# ecommerce/extensions/vouchers/management/commands/update_voucher_names.py
import logging
from time import sleep

from django.core.management.base import BaseCommand

from ecommerce.extensions.voucher.models import Voucher
from ecommerce.extensions.voucher.tasks import update_voucher_names, update_voucher_names_task

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update voucher names to be unique'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            action='store',
            dest='batch_size',
            type=int,
            default=1000,
            help='Number of vouchers to process in each batch'
        )
        parser.add_argument(
            '--run-async',
            action='store',
            dest='run_async',
            type=bool,
            default=False,
            help='Bool if this task is run on celery (default to False)'
        )
        parser.add_argument(
            '--batch-sleep',
            action='store',
            dest='batch_sleep',
            default=0,
            help='How long to sleep between batches.',
            type=int
        )
        parser.add_argument(
            '--batch-offset',
            action='store',
            dest='batch_offset',
            default=0,
            help='0-indexed offset to start processing at.',
            type=int
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        run_async = options['run_async']
        batch_sleep = options['batch_sleep']
        batch_offset = options['batch_offset']

        total_vouchers = Voucher.objects.count()
        processed_vouchers = batch_offset

        logger.info("Total number of vouchers: %d", total_vouchers)

        while processed_vouchers < total_vouchers:
            vouchers = Voucher.objects.all()[processed_vouchers:processed_vouchers + batch_size]
            try:
                # Call the Celery task asynchronously for each batch
                if run_async:
                    update_voucher_names_task.delay(vouchers)
                else:
                    update_voucher_names(vouchers)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Error updating voucher names: %s", exc)

            processed_vouchers += len(vouchers)
            logger.info("Processed %d out of %d vouchers", processed_vouchers, total_vouchers)

            sleep(batch_sleep)
