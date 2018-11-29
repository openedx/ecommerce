""" Django management command to find frozen baskets missing payment response. """

import logging
from datetime import datetime

import pytz
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q, Subquery
from oscar.core.loading import get_model

logger = logging.getLogger(__name__)
Basket = get_model('basket', 'Basket')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')


class InvalidDateRange(Exception):
    """
    Exception raised explicitly when end date is prior to start date
    """
    pass


class Command(BaseCommand):
    help = """
    Management command to find frozen baskets missing payment response

    This management command is responsible for checking the baskets
    and finding out the baskets for which the payment form was submitted.

    Date format: yyyy-mm-dd
    Start date should be prior to End date

    Example:
        $ ... find_frozen_baskets_missing_payment_response -s 2018-11-01 -e 2018-11-02

    Output:
        Frozen baskets missing payment response found
        Basket ID 7 Order Number EDX-100007
        Basket ID 20 Order Number EDX-100020
        Basket ID 1230 Order Number EDX-101230
        ...
    """

    def add_arguments(self, parser):
        parser.add_argument('-s', '--start-date',
                            dest='start_date',
                            required=True,
                            help='start date (yyyy-mm-dd)')
        parser.add_argument('-e', '--end-date',
                            dest='end_date',
                            required=True,
                            help='end date (yyyy-mm-dd)')

    def handle(self, *args, **options):
        """
        Handler for the command

        It checks for date format and range validity and then
        calls find_frozen_baskets_missing_payment_response for
        the given date range
        """
        try:
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d')
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d')
            if end_date < start_date:
                raise InvalidDateRange('Invalid date range')
        except (ValueError, InvalidDateRange):
            logger.exception('Incorrect date format or Range')
            raise

        start_date = pytz.utc.localize(start_date)
        end_date = pytz.utc.localize(end_date)

        self.find_frozen_baskets_missing_payment_response(start_date, end_date)

    def find_frozen_baskets_missing_payment_response(self, start_date, end_date):
        """ Find baskets that are Frozen and missing payment response """
        frozen_baskets = Basket.objects.filter(status='Frozen', date_submitted=None)
        frozen_baskets = frozen_baskets.filter(Q(date_created__range=(start_date, end_date)) |
                                               Q(date_merged__range=(start_date, end_date)))
        frozen_baskets_missing_payment_response = frozen_baskets.exclude(id__in=Subquery(
            PaymentProcessorResponse.objects.values_list('basket_id')))

        if not frozen_baskets_missing_payment_response:
            logger.info("No frozen baskets missing payment response found")
        else:
            logger.info("Frozen baskets missing payment response found")
            for basket in frozen_baskets_missing_payment_response:
                logger.info("Basket ID " + str(basket.id) + " Order Number " + str(basket.order_number))
            raise CommandError("Frozen baskets missing payment response found")
