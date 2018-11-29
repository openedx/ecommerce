""" Tests for Django management command to find frozen baskets missing payment response. """

from datetime import datetime, timedelta

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from oscar.core.loading import get_model
from testfixtures import LogCapture

from ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response import InvalidDateRange

Basket = get_model('basket', 'Basket')
PaymentProcessorResponse = get_model('payment', 'PaymentProcessorResponse')

LOGGER_NAME = 'ecommerce.core.management.commands.find_frozen_baskets_missing_payment_response'
command_args = '--start-date {start_date} --end-date {end_date}'


class FindFrozenBasketsMissingPaymentResponseTest(TestCase):
    """ Test the functionality of find_frozen_baskets_missing_payment_response command. """

    def test_invalid_command_arguments(self):
        """ Test command with invalid arguments """
        start_date = datetime.utcnow()
        end_date = datetime.utcnow() + timedelta(days=-1)

        # Invalid date format
        with self.assertRaises(ValueError):
            call_command(
                'find_frozen_baskets_missing_payment_response',
                *command_args.format(start_date=start_date.date(), end_date='30-11-2018').split(' ')
            )
        # End date prior to start date
        with self.assertRaises(InvalidDateRange):
            call_command(
                'find_frozen_baskets_missing_payment_response',
                *command_args.format(start_date=start_date.date(), end_date=end_date.date()).split(' ')
            )

    def test_date_submitted_not_NULL(self):
        """
        Tests that frozen baskets missing payment response are not returned when date_submission
        is not NULL
        """
        start_date = datetime.utcnow()
        end_date = datetime.utcnow() + timedelta(days=1)

        Basket.objects.create(
            status='Frozen',
            date_submitted=start_date,
            owner_id=1,
            site_id=1
        ).save()

        with LogCapture(LOGGER_NAME) as logger:
            call_command(
                'find_frozen_baskets_missing_payment_response',
                *command_args.format(start_date=start_date.date(), end_date=end_date.date()).split(' ')
            )
            logger.check(
                (LOGGER_NAME, 'INFO', 'No frozen baskets missing payment response found'),
            )

    def test_Payment_Processor_Response_found(self):
        """
        Test a basket when it's PaymentProcessorResponse is found.
        When a PaymentProcessorResponse is found basket is must not
        be returned
        """
        start_date = datetime.utcnow()
        end_date = datetime.utcnow() + timedelta(days=1)

        basket = Basket.objects.create(
            status='Frozen',
            date_submitted=None,
            owner_id=1,
            site_id=1
        )
        basket.order_number = 'EDX-00000'
        basket.save()
        PaymentProcessorResponse.objects.create(basket=basket)

        with LogCapture(LOGGER_NAME) as logger:
            call_command(
                'find_frozen_baskets_missing_payment_response',
                *command_args.format(start_date=start_date.date(), end_date=end_date.date()).split(' ')
            )
            logger.check(
                (LOGGER_NAME, 'INFO', 'No frozen baskets missing payment response found'),
            )

    def test_basket_out_of_date_range(self):
        """
        Tests when the Frozen basket is not in date range
        """
        start_date = datetime.utcnow()
        end_date = datetime.utcnow() + timedelta(days=1)

        basket = Basket.objects.create(
            status='Frozen',
            date_submitted=None,
            date_merged=start_date + timedelta(days=-1),
            owner_id=1,
            site_id=1
        )
        basket.date_created = start_date + timedelta(days=-1)
        basket.save()

        with LogCapture(LOGGER_NAME) as logger:
            call_command(
                'find_frozen_baskets_missing_payment_response',
                *command_args.format(start_date=start_date.date(), end_date=end_date.date()).split(' ')
            )
            logger.check(
                (LOGGER_NAME, 'INFO', 'No frozen baskets missing payment response found'),
            )

    def test_valid_arguments(self):
        """ Test command with valid arguments """
        start_date = datetime.utcnow()
        end_date = datetime.utcnow() + timedelta(days=1)

        Basket.objects.create(
            status='Frozen',
            date_submitted=None,
            date_merged=start_date,
            owner_id=1,
            site_id=1
        ).save()

        with self.assertRaises(CommandError):
            call_command(
                'find_frozen_baskets_missing_payment_response',
                *command_args.format(start_date=start_date.date(), end_date=end_date.date()).split(' ')
            )
