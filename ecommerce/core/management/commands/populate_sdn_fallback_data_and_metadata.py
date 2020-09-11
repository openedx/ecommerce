"""
Django management command to download SDN csv for use as fallback if the trade.gov API is down.
See docs/decisions/0007-sdn-fallback.rst for more details.

"""
import logging
import tempfile

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from requests.exceptions import Timeout

logger = logging.getLogger(__name__)


# commit 1
# commit 2
# commit 3
# commit 4
# commit 5
# commit 6
# commit 7
# commit 8
# commit 9

class Command(BaseCommand):
    help = 'Download the SDN csv from trade.gov, for use as fallback for when their SDN API is down.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--threshold',
            metavar='N',
            action='store',
            type=float,
            default=3,  # typical size is > 4 MB; 3 MB would be unexpectedly low
            help='File size MB threshold, under which we will not import it. Use default if argument not specified'
        )

    def handle(self, *args, **options):
        # download the csv locally, to check size and pass along to import
        threshold = options['threshold']
        url = 'http://api.trade.gov/static/consolidated_screening_list/consolidated.csv'
        timeout = settings.SDN_CHECK_REQUEST_TIMEOUT

        with requests.Session() as s:
            try:
                download = s.get(url, timeout=timeout)
                status_code = download.status_code
            except Timeout as e:
                logger.warning("SDN DOWNLOAD FAILURE: Timeout occurred trying to download SDN csv. Timeout threshold (in seconds): %s", timeout)  # pylint: disable=line-too-long
                raise
            except Exception as e:  # pylint: disable=broad-except
                logger.warning("SDN DOWNLOAD FAILURE: Exception occurred: [%s]", e)
                raise

            if download.status_code != 200:
                logger.warning("SDN DOWNLOAD FAILURE: Status code was: [%s]", status_code)
                raise Exception("CSV download url got an unsuccessful response code: ", status_code)

            with tempfile.TemporaryFile() as temp_csv:
                temp_csv.write(download.content)
                file_size_in_bytes = temp_csv.tell()  # get current position in the file (number of bytes)
                file_size_in_MB = file_size_in_bytes / 10**6

                if file_size_in_MB > threshold:
                    print("[TEMP]: CSV has eligible size, okay to import")
                    # ^ when import is ready (REV-1310), replace print statement with call to import with our csv
                else:
                    logger.warning("SDN DOWNLOAD FAILURE: file too small! (%f MB vs threshold of %s MB)", file_size_in_MB, threshold)   # pylint: disable=line-too-long
                    raise Exception("CSV file download did not meet threshold given")
