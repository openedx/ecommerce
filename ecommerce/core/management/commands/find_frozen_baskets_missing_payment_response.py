""" Django management command to find frozen baskets missing payment response. """

import logging
from datetime import datetime, timedelta

import pytz
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q, Subquery
from oscar.core.loading import get_model

logger = logging.getLogger(__name__)
Basket = get_model('basket', 'Basket')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')

DEFAULT_START_DELTA_TIME = 180
DEFAULT_END_DELTA_TIME = 60


class InvalidTimeRange(Exception):
    """
    Exception raised explicitly when End Time is prior to Start Time
    """
    pass


class Command(BaseCommand):
    help = """
    Management command to find frozen baskets missing payment response

    This management command is responsible for checking the baskets
    and finding out the baskets for which the payment form was submitted.

    start-delta : Minutes before now to start looking at frozen baskets that are missing
                  payment response
    end-delta : Minutes before now to end looking at frozen baskets that are missing payment
                response

    end-delta cannot be greater than start-delta

    Example:
        $ ... find_frozen_baskets_missing_payment_response --start-delta 240 --end-delta 60

    Output:
        Command Error: Frozen baskets missing payment response found
        Basket ID 7 Order Number EDX-100007
        Basket ID 20 Order Number EDX-100020
        Basket ID 1230 Order Number EDX-101230
        ...
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--start-delta',
            dest='start_delta',
            action='store',
            type=int,
            default=DEFAULT_START_DELTA_TIME,
            help='Minutes before now to start looking at baskets.'
        )
        parser.add_argument(
            '--end-delta',
            dest='end_delta',
            action='store',
            type=int,
            default=DEFAULT_END_DELTA_TIME,
            help='Minutes before now to end looking at baskets.'
        )

    def handle(self, *args, **options):
        """
        Handler for the command

        It checks for date format and range validity and then
        calls find_frozen_baskets_missing_payment_response for
        the given date range
        """
        start_delta = options['start_delta']
        end_delta = options['end_delta']

        try:
            if end_delta > start_delta:
                raise InvalidTimeRange('Invalid time range')
        except InvalidTimeRange:
            logger.exception('Incorrect Time Range')
            raise

        start = datetime.now(pytz.utc) - timedelta(minutes=start_delta)
        end = datetime.now(pytz.utc) - timedelta(minutes=end_delta)

        self.find_frozen_baskets_missing_payment_response(start, end)

    def find_frozen_baskets_missing_payment_response(self, start, end):
        """ Find baskets that are Frozen and missing payment response """
        frozen_baskets = Basket.objects.filter(status='Frozen', date_submitted=None)
        frozen_baskets = frozen_baskets.filter(Q(date_created__gte=start, date_created__lt=end) |
                                               Q(date_merged__gte=start, date_merged__lt=end))
        frozen_baskets_missing_payment_response = frozen_baskets.exclude(id__in=Subquery(
            PaymentProcessorResponse.objects.values_list('basket_id')))

        if not frozen_baskets_missing_payment_response:
            logger.info("No frozen baskets missing payment response found")
        else:
            logger.info("Frozen baskets missing payment response found")
            for basket in frozen_baskets_missing_payment_response:
                logger.info("Basket ID " + str(basket.id) + " Order Number " + str(basket.order_number))
            raise CommandError("Frozen baskets missing payment response found")
