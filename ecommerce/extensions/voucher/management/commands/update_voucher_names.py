# ecommerce/extensions/vouchers/management/commands/update_voucher_names.py
import logging

from django.core.management.base import BaseCommand

from ecommerce.extensions.voucher.models import Voucher
from ecommerce.extensions.voucher.tasks import update_voucher_names

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update voucher names asynchronously'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=1000, help='Number of vouchers to process in each batch')

    def handle(self, *args, **options):
        batch_size = options['batch_size']

        total_vouchers = Voucher.objects.count()
        processed_vouchers = 0

        logger.info("Total number of vouchers: %d", total_vouchers)

        while processed_vouchers < total_vouchers:
            vouchers = Voucher.objects.all()[processed_vouchers:processed_vouchers + batch_size]
            try:
                # Call the Celery task asynchronously for each batch
                update_voucher_names.delay(vouchers)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Error updating voucher names: %s", exc)

            processed_vouchers += len(vouchers)
            logger.info("Processed %d out of %d vouchers", processed_vouchers, total_vouchers)
