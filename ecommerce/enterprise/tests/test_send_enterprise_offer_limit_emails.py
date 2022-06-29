# encoding: utf-8
"""
Contains the tests for sending the enterprise offer limit emails command.
"""
import datetime
from urllib.parse import urljoin

import mock
import responses
from django.conf import settings
from django.core.management import call_command

from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.test.factories import EnterpriseOfferFactory
from ecommerce.programs.custom import get_model
from ecommerce.tests.mixins import SiteMixin
from ecommerce.tests.testcases import TestCase

ConditionalOffer = get_model('offer', 'ConditionalOffer')
OfferUsageEmail = get_model('offer', 'OfferUsageEmail')

COMMAND_PATH = 'ecommerce.enterprise.management.commands.send_enterprise_offer_limit_emails'
LOGGER_NAME = COMMAND_PATH


class SendEnterpriseOfferLimitEmailsTests(TestCase, SiteMixin, EnterpriseServiceMockMixin):
    """
    Tests the sending the enterprise offer limit emails command.
    """

    def setUp(self):
        """
        Create test data.
        """
        super(SendEnterpriseOfferLimitEmailsTests, self).setUp()

        self.mock_access_token_response()

        self.offer_1 = EnterpriseOfferFactory(max_discount=100)
        self.offer_2 = EnterpriseOfferFactory(max_discount=100)

        # Make two more offers that are not eligible for alerts
        # by setting their max applications/discounts to 0.
        EnterpriseOfferFactory(max_global_applications=0)
        EnterpriseOfferFactory(max_discount=0)

        # Creating conditionaloffer with daily frequency and adding corresponding offer_usage object.
        self.offer_with_daily_frequency = EnterpriseOfferFactory(max_global_applications=10)
        offer_usage = OfferUsageEmail.create_record(self.offer_with_daily_frequency)
        offer_usage.created = datetime.datetime.fromordinal(datetime.datetime.now().toordinal() - 2)
        offer_usage.save()

        # Creating conditionaloffer with weekly frequency and adding corresponding offer_usage object.
        self.offer_with_weekly_frequency = EnterpriseOfferFactory(
            max_global_applications=10,
            usage_email_frequency=ConditionalOffer.WEEKLY
        )
        offer_usage = OfferUsageEmail.create_record(self.offer_with_weekly_frequency)
        offer_usage.created = datetime.datetime.fromordinal(datetime.datetime.now().toordinal() - 8)
        offer_usage.save()

        # Creating conditionaloffer with monthly frequency and adding corresponding offer_usage object.
        self.offer_with_monthly_frequency = EnterpriseOfferFactory(
            max_global_applications=10,
            usage_email_frequency=ConditionalOffer.MONTHLY
        )
        offer_usage = OfferUsageEmail.create_record(self.offer_with_monthly_frequency)
        offer_usage.created = datetime.datetime.fromordinal(datetime.datetime.now().toordinal() - 31)
        offer_usage.save()

        # Add an offer that is eligible for the usage email,
        # but has no corresponding mock response configured,
        # so that it hits a 404 and is appropriately handled by the try/except
        # block for RequestExceptions inside the command's handle() method.
        self.offer_with_404 = EnterpriseOfferFactory(max_discount=100)

    def mock_lms_user_responses(self, user_ids_by_email):
        api_url = urljoin(f"{self.site.siteconfiguration.user_api_url}/", "accounts/search_emails")

        for _, user_id in user_ids_by_email.items():
            responses.add(
                responses.POST,
                api_url,
                json=[{'id': user_id}],
                content_type='application/json',
            )

    def mock_offer_analytics_response(self, enterprise_uuid, offer_id):
        route = f'/enterprise/api/v1/enterprise/{enterprise_uuid}/offers/{offer_id}/'
        api_url = f'{settings.ENTERPRISE_ANALYTICS_API_URL}{route}'
        responses.add(
            responses.GET,
            api_url,
            json={
                'max_discount': 10000.0,
                'percent_of_offer_spent': 50.0,
                'amount_of_offer_spent': 5000.0,
            },
            content_type='application/json',
        )

    @responses.activate
    def test_command(self):
        """
        Test the send_enterprise_offer_limit_emails command
        """
        offer_usage_count = OfferUsageEmail.objects.all().count()
        admin_email_1, admin_email_2 = 'example_1@example.com', 'example_2@example.com'
        self.mock_lms_user_responses({
            admin_email_1: 22,
            admin_email_2: 44,
        })

        # Don't mock out a response for self.offer_with_404
        for offer in ConditionalOffer.objects.exclude(id=self.offer_with_404.id):
            self.mock_offer_analytics_response(offer.condition.enterprise_customer_uuid, offer.id)

        with mock.patch(COMMAND_PATH + '.send_offer_usage_email.delay') as mock_send_email:
            mock_send_email.return_value = mock.Mock()
            call_command('send_enterprise_offer_limit_emails')
            # if self.offer_with_404 had email content, this 5 would be a 6.
            assert mock_send_email.call_count == 5
            assert OfferUsageEmail.objects.all().count() == offer_usage_count + 5

            mock_send_email.assert_has_calls([
                mock.call(
                    {'example_1@example.com': 22, ' example_2@example.com': 44},
                    'Offer Usage Notification',
                    {'percent_usage': 50.0, 'total_limit': '$10000.0', 'offer_type': 'Booking',
                     'offer_name': self.offer_1.name, 'current_usage': '$5000.0'}
                ),
                mock.call().get(propagate=False),
                mock.call().successful(),
                mock.call(
                    {'example_1@example.com': 44, ' example_2@example.com': 44},
                    'Offer Usage Notification',
                    {'percent_usage': 50.0, 'total_limit': '$10000.0', 'offer_type': 'Booking',
                     'offer_name': self.offer_2.name, 'current_usage': '$5000.0'}
                ),
                mock.call().get(propagate=False),
                mock.call().successful(),
                mock.call(
                    {'example_1@example.com': 44, ' example_2@example.com': 44},
                    'Offer Usage Notification',
                    {'percent_usage': 0, 'total_limit': 10, 'offer_type': 'Enrollment',
                     'offer_name': self.offer_with_daily_frequency.name, 'current_usage': 0}
                ),
                mock.call().get(propagate=False),
                mock.call().successful(),
                mock.call(
                    {'example_1@example.com': 44, ' example_2@example.com': 44},
                    'Offer Usage Notification',
                    {'percent_usage': 0, 'total_limit': 10, 'offer_type': 'Enrollment',
                     'offer_name': self.offer_with_weekly_frequency.name, 'current_usage': 0}
                ),
                mock.call().get(propagate=False),
                mock.call().successful(),
                mock.call(
                    {'example_1@example.com': 44, ' example_2@example.com': 44},
                    'Offer Usage Notification',
                    {'percent_usage': 0, 'total_limit': 10, 'offer_type': 'Enrollment',
                     'offer_name': self.offer_with_monthly_frequency.name, 'current_usage': 0}
                ),
                mock.call().get(propagate=False),
                mock.call().successful(),
            ])

    @responses.activate
    def test_command_single_enterprise(self):
        """
        Test the send_enterprise_offer_limit_emails command on a single enterprise customer.
        """
        offer_usage_count = OfferUsageEmail.objects.all().count()
        admin_email_1, admin_email_2 = 'example_1@example.com', 'example_2@example.com'
        self.mock_lms_user_responses({
            admin_email_1: 22,
            admin_email_2: 44,
        })

        customer_uuid = self.offer_1.condition.enterprise_customer_uuid
        self.mock_offer_analytics_response(customer_uuid, self.offer_1.id)

        with mock.patch(COMMAND_PATH + '.send_offer_usage_email.delay') as mock_send_email:
            mock_send_email.return_value = mock.Mock()
            call_command('send_enterprise_offer_limit_emails', enterprise_customer_uuid=customer_uuid)
            # if self.offer_with_404 had email content, this 5 would be a 6.
            assert mock_send_email.call_count == 1
            assert OfferUsageEmail.objects.all().count() == offer_usage_count + 1

            mock_send_email.assert_has_calls([
                mock.call(
                    {'example_1@example.com': 22, ' example_2@example.com': 44},
                    'Offer Usage Notification',
                    {'percent_usage': 50.0, 'total_limit': '$10000.0', 'offer_type': 'Booking',
                     'offer_name': self.offer_1.name, 'current_usage': '$5000.0'}
                ),
                mock.call().get(propagate=False),
                mock.call().successful(),
            ])
