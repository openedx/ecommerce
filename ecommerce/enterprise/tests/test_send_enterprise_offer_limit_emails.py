# encoding: utf-8
"""
Contains the tests for sending the enterprise offer limit emails command.
"""
import datetime
import logging

import mock
from django.core.management import call_command
from testfixtures import LogCapture

from ecommerce.extensions.test.factories import EnterpriseOfferFactory
from ecommerce.programs.custom import get_model
from ecommerce.tests.testcases import TestCase

ConditionalOffer = get_model('offer', 'ConditionalOffer')
OfferUsageEmail = get_model('offer', 'OfferUsageEmail')

LOGGER_NAME = 'ecommerce.enterprise.management.commands.send_enterprise_offer_limit_emails'


class SendEnterpriseOfferLimitEmailsTests(TestCase):
    """
    Tests the sending the enterprise offer limit emails command.
    """

    def setUp(self):
        """
        Create test data.
        """
        super(SendEnterpriseOfferLimitEmailsTests, self).setUp()

        EnterpriseOfferFactory(max_global_applications=10)
        EnterpriseOfferFactory(max_discount=100)
        EnterpriseOfferFactory(max_global_applications=0)
        EnterpriseOfferFactory(max_discount=0)

        # Creating conditionaloffer with daily frequency and adding corresponding offer_usage object.
        offer_with_daily_frequency = EnterpriseOfferFactory(max_global_applications=10)
        offer_usage = OfferUsageEmail.create_record(offer_with_daily_frequency)
        offer_usage.created = datetime.datetime.fromordinal(datetime.datetime.now().toordinal() - 2)
        offer_usage.save()

        # Creating conditionaloffer with weekly frequency and adding corresponding offer_usage object.
        offer_with_weekly_frequency = EnterpriseOfferFactory(
            max_global_applications=10,
            usage_email_frequency=ConditionalOffer.WEEKLY
        )
        offer_usage = OfferUsageEmail.create_record(offer_with_weekly_frequency)
        offer_usage.created = datetime.datetime.fromordinal(datetime.datetime.now().toordinal() - 8)
        offer_usage.save()

        # Creating conditionaloffer with monthly frequency and adding corresponding offer_usage object.
        offer_with_monthly_frequency = EnterpriseOfferFactory(
            max_global_applications=10,
            usage_email_frequency=ConditionalOffer.MONTHLY
        )
        offer_usage = OfferUsageEmail.create_record(offer_with_monthly_frequency)
        offer_usage.created = datetime.datetime.fromordinal(datetime.datetime.now().toordinal() - 31)
        offer_usage.save()

    def test_command(self):
        """
        Test the send_enterprise_offer_limit_emails command
        """
        offer_usage_count = OfferUsageEmail.objects.all().count()
        with mock.patch('ecommerce_worker.sailthru.v1.tasks.send_offer_usage_email.delay') as mock_send_email:
            with LogCapture(level=logging.INFO) as log:
                mock_send_email.return_value = mock.Mock()
                call_command('send_enterprise_offer_limit_emails')
                assert mock_send_email.call_count == 5
                assert OfferUsageEmail.objects.all().count() == offer_usage_count + 5
        log.check_present(
            (
                LOGGER_NAME,
                'INFO',
                '[Offer Usage Alert] Total count of enterprise offers is {total_enterprise_offers_count}.'.format(
                    total_enterprise_offers_count=7
                )
            ),
            (
                LOGGER_NAME,
                'INFO',
                '[Offer Usage Alert] {total_enterprise_offers_count} of {send_enterprise_offer_count} added to the'
                ' email sending queue.'.format(
                    total_enterprise_offers_count=7,
                    send_enterprise_offer_count=5
                )
            )
        )
