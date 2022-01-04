"""
This command runs create_or_update_seat on all seats that contain 'ID verification' in the title.
"""
import logging
import time

from django.core.management import BaseCommand
from oscar.apps.partner.strategy import Selector

from ecommerce.courses.models import Course
from ecommerce.extensions.catalogue.models import Product

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Run create_or_update_seat on seats containing 'ID verification'."""

    help = 'Run create_or_update_seat on all seats that contain "ID verification" in the title'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='Maximum number of seats to update in one batch')
        parser.add_argument(
            '--sleep-time',
            type=int,
            default=10,
            help='Sleep time in seconds between update of batches')

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        sleep_time = options['sleep_time']
        succeeded = 0
        failed = 0

        seats = Product.objects.filter(title__icontains='ID verification')
        total_seats = len(seats)
        logger.info(
            'Updating a total of %d seats that contain "ID verification" in the title.',
            total_seats
        )

        batch_seats = []

        for seat in seats:
            batch_seats.append(seat)

            if len(batch_seats) == batch_size:
                succeeded, failed = self._update_seats(batch_seats, succeeded, failed)
                time.sleep(sleep_time)
                batch_seats = []

        if len(batch_seats) > 0:
            succeeded, failed = self._update_seats(batch_seats, succeeded, failed)

        logger.info('Seat update complete. %d succeeded, %d failed.', succeeded, failed)

    def _update_seats(self, batch_seats, succeeded, failed):
        strategy = Selector().strategy()

        for seat in batch_seats:
            info = strategy.fetch_for_product(seat)

            try:
                course = Course.objects.get(id=seat.attr.course_key)
                course.create_or_update_seat(
                    seat.attr.certificate_type,
                    seat.attr.id_verification_required,
                    info.price.excl_tax,
                    expires=seat.expires,
                    sku=info.stockrecord.partner_sku
                )
                succeeded += 1
            except Exception:  # pylint: disable=broad-except
                logger.error(
                    'Could not update seat title="%s" in course_id="%s".',
                    seat.title, seat.attr.course_key
                )
                failed += 1

        return succeeded, failed
