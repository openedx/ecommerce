"""
Django management command to download SDN csv for use as fallback if the trade.gov API is down.

"""
import logging
import os

from django.core.management.base import BaseCommand, CommandError

from ecommerce.extensions.payment.utils import download_SDN_fallback_csv

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Management command to download csv for use as fallback for SDN check.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            metavar='N',
            action='store',
            type=float,
            default=3,
            help='File size MB threshold, under which we will not import it. Use default if argument not specified'
        )

    def handle(self, *args, **options):
        # download the csv locally, to check size and pass along to import
        threshold = options['threshold']

        csv, csv_file_size_in_MB, csv_file_name = download_SDN_fallback_csv()

        try:
            assert csv_file_size_in_MB > threshold
            # [placeholder] call the import for the csv here (REV-1310)
        except:
            logger.warning("CSV file download did not meet threshold")
            raise CommandError("CSV file download did not meet threshold")
        finally:
            os.remove(csv_file_name)
