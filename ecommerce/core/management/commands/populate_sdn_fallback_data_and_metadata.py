"""
Django management command to download SDN csv for use as fallback if the trade.gov API is down.
See docs/decisions/0007-sdn-fallback.rst for more details.

"""
import logging
import os
import requests

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Download the SDN csv from trade.gov, for use as fallback for when their SDN API is down.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            metavar='N',
            action='store',
            type=float,
            default=3,
            help='File size MB threshold, under which we will not import it. Use default if argument not specified'
        )
        parser.add_argument(
            '--url',
            metavar='N',
            action='store',
            type=str,
            default='http://api.trade.gov/static/consolidated_screening_list/consolidated.csv',
            help='Url to call for SDN csv, default to trade.gov'
        )

    def handle(self, *args, **options):
        # download the csv locally, to check size and pass along to import
        threshold = options['threshold']
        url = options['url']
        csv_file_name = 'temp_sdn_fallback.csv'

        with requests.Session() as s:
            try:
                download = s.get(url)
            except Exception as e:   # pylint: disable=broad-except
                logger.warning("Exception occurred: [%s]", e)
                raise CommandError("Exception occurred")

            csv = open(csv_file_name, 'wb')
            csv.write(download.content)
            csv.close()
            file_size_in_bytes = os.path.getsize(csv_file_name)
            file_size_in_MB = file_size_in_bytes / 10**6

            if file_size_in_MB > threshold:
                print("[TEMP]: csv has eligible size, okay to import")
                # ^ when import is ready (REV-1310), replace print statement with call to import with our csv
            else:
                logger.warning("CSV file download did not meet threshold given: [%f]", threshold)
                raise CommandError("CSV file download did not meet threshold")
            os.remove(csv_file_name)

