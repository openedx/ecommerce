""" Tests for Django management command to find frozen baskets missing payment response. """

from datetime import datetime, timedelta

import pytz
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from oscar.core.loading import get_model
from testfixtures import LogCapture

from ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response import (
    DEFAULT_START_DELTA_TIME,
    InvalidTimeRange
)
from ecommerce.tests.mixins import SiteMixin


Basket = get_model('basket', 'Basket')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')

LOGGER_NAME = 'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response'


class FindFrozenBasketsMissingPaymentResponseTest(SiteMixin, TestCase):
    """ Test the functionality of find_frozen_baskets_missing_payment_response command. """

    def test_invalid_command_arguments(self):
        """ Test command with invalid arguments """

        with self.assertRaises(InvalidTimeRange):
            call_command(
                'find_frozen_baskets_missing_payment_response',
                start_delta=60, end_delta=240
            )

    def test_date_submitted_not_NULL(self):
        """
        Tests that frozen baskets missing payment response are not returned when date_submission
        is not NULL
        """
        date_submitted = datetime.utcnow()

        Basket.objects.create(
            status='Frozen',
            date_submitted=date_submitted,
            owner_id=1
        ).save()

        with LogCapture(LOGGER_NAME) as logger:
            call_command('find_frozen_baskets_missing_payment_response')
            logger.check(
                (LOGGER_NAME, 'INFO', 'No frozen baskets missing payment response found'),
            )

    def test_Payment_Processor_Response_found(self):
        """
        Test a basket when it's PaymentProcessorResponse is found.
        When a PaymentProcessorResponse is found basket must not
        be returned
        """
        basket = Basket.objects.create(
            status='Frozen',
            date_submitted=None,
            owner_id=1
        ).save()
        PaymentProcessorResponse.objects.create(basket=basket)

        with LogCapture(LOGGER_NAME) as logger:
            call_command('find_frozen_baskets_missing_payment_response')
            logger.check(
                (LOGGER_NAME, 'INFO', 'No frozen baskets missing payment response found'),
            )

    def test_time_window(self):
        """
        Tests when the Frozen basket is not in time range
        """
        time_outside_window = DEFAULT_START_DELTA_TIME + 1
        time_outside_window_datetime = datetime.now(pytz.utc) - timedelta(minutes=time_outside_window)

        basket = Basket.objects.create(
            status='Frozen',
            date_submitted=None,
            date_merged=time_outside_window_datetime,
            owner_id=1
        )
        basket.date_created = time_outside_window_datetime
        basket.save()

        with LogCapture(LOGGER_NAME) as logger:
            call_command('find_frozen_baskets_missing_payment_response')
            logger.check(
                (LOGGER_NAME, 'INFO', 'No frozen baskets missing payment response found'),
            )

    def test_valid_arguments(self):
        """ Test command with valid arguments """
        time_in_window = DEFAULT_START_DELTA_TIME - 1
        time_in_window_datetime = datetime.now(pytz.utc) - timedelta(minutes=time_in_window)

        Basket.objects.create(
            status='Frozen',
            date_submitted=None,
            date_merged=time_in_window_datetime,
            owner_id=1,
        ).save()

        with self.assertRaises(CommandError):
            call_command('find_frozen_baskets_missing_payment_response')
