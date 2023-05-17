# encoding: utf-8
"""
Contains the tests for sending the enterprise offer limit emails command.
"""
import datetime
import logging
from urllib.parse import urljoin

import mock
import responses
from django.conf import settings
from django.core.management import call_command
from testfixtures import LogCapture

from ecommerce.enterprise.tests.mixins import EnterpriseServiceMockMixin
from ecommerce.extensions.offer.constants import OfferUsageEmailTypes
from ecommerce.extensions.test.factories import EnterpriseOfferFactory
from ecommerce.programs.custom import get_model
from ecommerce.tests.mixins import SiteMixin
from ecommerce.tests.testcases import TestCase

ConditionalOffer = get_model('offer', 'ConditionalOffer')
OfferUsageEmail = get_model('offer', 'OfferUsageEmail')

BASE_COMMAND_PATH = 'ecommerce.enterprise.management.commands'
API_TRIGGERED_PATH = BASE_COMMAND_PATH + '.send_api_triggered_offer_emails'
DEPRECATED_PATH = BASE_COMMAND_PATH + '.send_enterprise_offer_limit_emails'


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

    def mock_lms_user_responses(self, user_ids_by_email):
        api_url = urljoin(f"{self.site.siteconfiguration.user_api_url}/", "accounts/search_emails")

        for _, user_id in user_ids_by_email.items():
            responses.add(
                responses.POST,
                api_url,
                json=[{'id': user_id}],
                content_type='application/json',
            )

    def mock_offer_analytics_response(
        self,
        enterprise_uuid,
        offer_id,
        max_discount=10000.0,
        amount_of_offer_spent=5000.0,
        remaining_balance=5000.0
    ):
        route = f'/enterprise/api/v1/enterprise/{enterprise_uuid}/offers/{offer_id}/'
        api_url = f'{settings.ENTERPRISE_ANALYTICS_API_URL}{route}'
        responses.add(
            responses.GET,
            api_url,
            json={
                'max_discount': max_discount,
                'percent_of_offer_spent': (amount_of_offer_spent / max_discount),
                'amount_of_offer_spent': amount_of_offer_spent,
                'remaining_balance': remaining_balance,
            },
            content_type='application/json',
        )

    @responses.activate
    def test_low_balance_email(self):
        admin_email = 'example_1@example.com'

        offer_with_low_balance = EnterpriseOfferFactory(max_discount=100, emails_for_usage_alert=admin_email)

        offer_with_low_balance_email_sent_before = EnterpriseOfferFactory(
            max_discount=100, emails_for_usage_alert=admin_email
        )
        OfferUsageEmail.create_record(
            OfferUsageEmailTypes.LOW_BALANCE,
            offer_with_low_balance_email_sent_before,
            {
                'email_usage_data': {
                    'total_limit': 10000.0
                }
            }
        ).save()

        replenished_offer_with_low_balance_email_sent_before = EnterpriseOfferFactory(
            max_discount=100,
            emails_for_usage_alert=admin_email,
        )
        OfferUsageEmail.create_record(
            OfferUsageEmailTypes.LOW_BALANCE,
            replenished_offer_with_low_balance_email_sent_before,
            {
                'email_usage_data': {
                    'total_limit': 10000.0
                }
            }
        ).save()

        self.mock_lms_user_responses({
            admin_email: 22,
        })

        self.mock_offer_analytics_response(
            offer_with_low_balance.condition.enterprise_customer_uuid,
            offer_with_low_balance.id,
            amount_of_offer_spent=7500.0,
            remaining_balance=2500.0,
        )

        # low balance email sent before, should result in digest email
        self.mock_offer_analytics_response(
            offer_with_low_balance_email_sent_before.condition.enterprise_customer_uuid,
            offer_with_low_balance_email_sent_before.id,
            amount_of_offer_spent=7500.0,
            remaining_balance=2500.0,
        )

        # low balance email sent before but offer is replenished, should send low balance email again
        self.mock_offer_analytics_response(
            replenished_offer_with_low_balance_email_sent_before.condition.enterprise_customer_uuid,
            replenished_offer_with_low_balance_email_sent_before.id,
            amount_of_offer_spent=15000.0,
            max_discount=20000.0,
        )

        with mock.patch(API_TRIGGERED_PATH + '.send_api_triggered_offer_usage_email.delay') as mock_send_email:
            mock_send_email.return_value = mock.Mock()
            call_command('send_api_triggered_offer_emails')
            assert mock_send_email.call_count == 3

            mock_send_email.assert_has_calls([
                mock.call(
                    {'example_1@example.com': 22},
                    'Offer Usage Notification',
                    {
                        'email_type': OfferUsageEmailTypes.LOW_BALANCE, 'is_enrollment_limit_offer': False,
                        'percent_usage': 75.0, 'total_limit': 10000.0, 'total_limit_str': '$10,000.00',
                        'offer_type': 'Booking', 'offer_name': offer_with_low_balance.name,
                        'current_usage': 7500.0, 'current_usage_str': '$7,500.00',
                        'remaining_balance': 2500.0, 'remaining_balance_str': '$2,500.00',
                        'enterprise_customer_name': offer_with_low_balance.condition.enterprise_customer_name,
                    },
                    campaign_id=settings.CAMPAIGN_IDS_BY_EMAIL_TYPE[OfferUsageEmailTypes.LOW_BALANCE]
                ),
                mock.call(
                    {'example_1@example.com': 22},
                    'Offer Usage Notification',
                    {
                        'email_type': OfferUsageEmailTypes.DIGEST, 'is_enrollment_limit_offer': False,
                        'percent_usage': 75.0, 'total_limit': 10000.0, 'total_limit_str': '$10,000.00',
                        'offer_type': 'Booking', 'offer_name': offer_with_low_balance_email_sent_before.name,
                        'current_usage': 7500.0, 'current_usage_str': '$7,500.00',
                        'remaining_balance': 2500.0, 'remaining_balance_str': '$2,500.00',
                        'enterprise_customer_name':
                            offer_with_low_balance_email_sent_before.condition.enterprise_customer_name,
                    },
                    campaign_id=settings.CAMPAIGN_IDS_BY_EMAIL_TYPE[OfferUsageEmailTypes.DIGEST]
                ),
                mock.call(
                    {'example_1@example.com': 22},
                    'Offer Usage Notification',
                    {
                        'email_type': OfferUsageEmailTypes.LOW_BALANCE, 'is_enrollment_limit_offer': False,
                        'percent_usage': 75.0, 'total_limit': 20000.0, 'total_limit_str': '$20,000.00',
                        'offer_type': 'Booking',
                        'offer_name': replenished_offer_with_low_balance_email_sent_before.name,
                        'current_usage': 15000.0, 'current_usage_str': '$15,000.00',
                        'remaining_balance': 5000.0, 'remaining_balance_str': '$5,000.00',
                        'enterprise_customer_name':
                            replenished_offer_with_low_balance_email_sent_before.condition.enterprise_customer_name,
                    },
                    campaign_id=settings.CAMPAIGN_IDS_BY_EMAIL_TYPE[OfferUsageEmailTypes.LOW_BALANCE]
                ),
            ])

    @responses.activate
    def test_no_balance_email(self):
        admin_email = 'example_1@example.com'

        offer_with_no_balance = EnterpriseOfferFactory(max_discount=100, emails_for_usage_alert=admin_email)

        offer_with_no_balance_email_sent_before = EnterpriseOfferFactory(
            max_discount=100, emails_for_usage_alert=admin_email
        )

        OfferUsageEmail.create_record(
            OfferUsageEmailTypes.OUT_OF_BALANCE,
            offer_with_no_balance_email_sent_before,
            {
                'email_usage_data': {
                    'total_limit': 10000.0
                }
            }
        ).save()

        replenished_offer_with_no_balance_email_sent_before = EnterpriseOfferFactory(
            max_discount=100,
            emails_for_usage_alert=admin_email,
        )
        OfferUsageEmail.create_record(
            OfferUsageEmailTypes.OUT_OF_BALANCE,
            replenished_offer_with_no_balance_email_sent_before,
            {
                'email_usage_data': {
                    'total_limit': 10000.0
                }
            }
        ).save()

        self.mock_lms_user_responses({
            admin_email: 22,
        })

        self.mock_offer_analytics_response(
            offer_with_no_balance.condition.enterprise_customer_uuid,
            offer_with_no_balance.id,
            amount_of_offer_spent=9900.0,
            remaining_balance=100.0,
        )

        # no balance email sent before, should result in no email
        self.mock_offer_analytics_response(
            offer_with_no_balance_email_sent_before.condition.enterprise_customer_uuid,
            offer_with_no_balance_email_sent_before.id,
            amount_of_offer_spent=9900.0,
            remaining_balance=100.0,
        )

        # no balance email sent before but offer is replenished, should send no balance email again
        self.mock_offer_analytics_response(
            replenished_offer_with_no_balance_email_sent_before.condition.enterprise_customer_uuid,
            replenished_offer_with_no_balance_email_sent_before.id,
            amount_of_offer_spent=19900.0,
            max_discount=20000.0,
            remaining_balance=100.0,
        )

        with mock.patch(API_TRIGGERED_PATH + '.send_api_triggered_offer_usage_email.delay') as mock_send_email:
            mock_send_email.return_value = mock.Mock()
            call_command('send_api_triggered_offer_emails')
            assert mock_send_email.call_count == 2
            mock_send_email.assert_has_calls([
                mock.call(
                    {'example_1@example.com': 22},
                    'Offer Usage Notification',
                    {
                        'email_type': OfferUsageEmailTypes.OUT_OF_BALANCE, 'is_enrollment_limit_offer': False,
                        'percent_usage': 99.0, 'total_limit_str': '$10,000.00', 'total_limit': 10000.0,
                        'offer_type': 'Booking', 'offer_name': offer_with_no_balance.name,
                        'current_usage': 9900.0, 'current_usage_str': '$9,900.00',
                        'remaining_balance': 100.0, 'remaining_balance_str': '$100.00',
                        'enterprise_customer_name': offer_with_no_balance.condition.enterprise_customer_name,
                    },
                    campaign_id=settings.CAMPAIGN_IDS_BY_EMAIL_TYPE[OfferUsageEmailTypes.OUT_OF_BALANCE]
                ),
                mock.call(
                    {'example_1@example.com': 22},
                    'Offer Usage Notification',
                    {
                        'email_type': OfferUsageEmailTypes.OUT_OF_BALANCE, 'is_enrollment_limit_offer': False,
                        'percent_usage': 99.5, 'total_limit_str': '$20,000.00', 'total_limit': 20000.0,
                        'offer_type': 'Booking', 'offer_name': replenished_offer_with_no_balance_email_sent_before.name,
                        'current_usage': 19900.0, 'current_usage_str': '$19,900.00',
                        'remaining_balance': 100.0, 'remaining_balance_str': '$100.00',
                        'enterprise_customer_name':
                            replenished_offer_with_no_balance_email_sent_before.condition.enterprise_customer_name,
                    },
                    campaign_id=settings.CAMPAIGN_IDS_BY_EMAIL_TYPE[OfferUsageEmailTypes.OUT_OF_BALANCE]
                ),
            ])

    @responses.activate
    def test_digest_email(self):
        """
        Test the send_api_triggered_offer_emails command
        """

        offer_1 = EnterpriseOfferFactory(max_discount=100)
        offer_2 = EnterpriseOfferFactory(max_discount=100)

        # Make two more offers that are not eligible for alerts
        # by setting their max applications/discounts to 0.
        EnterpriseOfferFactory(max_global_applications=0)
        EnterpriseOfferFactory(max_discount=0)

        # Creating conditionaloffer with daily frequency and adding corresponding offer_usage object.
        offer_with_daily_frequency = EnterpriseOfferFactory(max_global_applications=10)
        offer_usage = OfferUsageEmail.create_record(OfferUsageEmailTypes.DIGEST, offer_with_daily_frequency)
        offer_usage.created = datetime.datetime.fromordinal(datetime.datetime.now().toordinal() - 2)
        offer_usage.save()

        # Creating conditionaloffer with weekly frequency and adding corresponding offer_usage object.
        offer_with_weekly_frequency = EnterpriseOfferFactory(
            max_global_applications=10,
            usage_email_frequency=ConditionalOffer.WEEKLY
        )
        offer_usage = OfferUsageEmail.create_record(OfferUsageEmailTypes.DIGEST, offer_with_weekly_frequency)
        offer_usage.created = datetime.datetime.fromordinal(datetime.datetime.now().toordinal() - 8)
        offer_usage.save()

        # Creating conditionaloffer with monthly frequency and adding corresponding offer_usage object.
        offer_with_monthly_frequency = EnterpriseOfferFactory(
            max_global_applications=10,
            usage_email_frequency=ConditionalOffer.MONTHLY
        )
        offer_usage = OfferUsageEmail.create_record(OfferUsageEmailTypes.DIGEST, offer_with_monthly_frequency)
        offer_usage.created = datetime.datetime.fromordinal(datetime.datetime.now().toordinal() - 31)
        offer_usage.save()

        # Add an offer that is eligible for the usage email,
        # but has no corresponding mock response configured,
        # so that it hits a 404 and is appropriately handled by the try/except
        # block for RequestExceptions inside the command's handle() method.
        offer_with_404 = EnterpriseOfferFactory(max_discount=100)

        offer_usage_count = OfferUsageEmail.objects.all().count()

        admin_email_1, admin_email_2 = 'example_1@example.com', 'example_2@example.com'
        self.mock_lms_user_responses({
            admin_email_1: 22,
            admin_email_2: 44,
        })

        # Don't mock out a response for certain offers
        for offer in ConditionalOffer.objects.exclude(id=offer_with_404.id):
            self.mock_offer_analytics_response(offer.condition.enterprise_customer_uuid, offer.id)

        with mock.patch(API_TRIGGERED_PATH + '.send_api_triggered_offer_usage_email.delay') as mock_send_email:
            mock_send_email.return_value = mock.Mock()
            call_command('send_api_triggered_offer_emails')
            # if offer_with_404 had email content, this 5 would be a 6.
            assert mock_send_email.call_count == 5
            assert OfferUsageEmail.objects.all().count() == offer_usage_count + 5
            mock_send_email.assert_has_calls([
                mock.call(
                    {'example_1@example.com': 22, ' example_2@example.com': 44},
                    'Offer Usage Notification',
                    {
                        'email_type': OfferUsageEmailTypes.DIGEST, 'is_enrollment_limit_offer': False,
                        'percent_usage': 50.0, 'total_limit_str': '$10,000.00', 'offer_type': 'Booking',
                        'total_limit': 10000.0, 'offer_name': offer_1.name, 'current_usage': 5000.0,
                        'current_usage_str': '$5,000.00',
                        'remaining_balance': 5000.0, 'remaining_balance_str': '$5,000.00',
                        'enterprise_customer_name': offer_1.condition.enterprise_customer_name,
                    },
                    campaign_id=settings.CAMPAIGN_IDS_BY_EMAIL_TYPE[OfferUsageEmailTypes.DIGEST]
                ),
                mock.call(
                    {'example_1@example.com': 44, ' example_2@example.com': 44},
                    'Offer Usage Notification',
                    {
                        'email_type': OfferUsageEmailTypes.DIGEST, 'is_enrollment_limit_offer': False,
                        'percent_usage': 50.0, 'total_limit_str': '$10,000.00', 'total_limit': 10000.0,
                        'offer_type': 'Booking', 'offer_name': offer_2.name, 'current_usage': 5000.0,
                        'current_usage_str': '$5,000.00',
                        'remaining_balance': 5000.0, 'remaining_balance_str': '$5,000.00',
                        'enterprise_customer_name': offer_2.condition.enterprise_customer_name,
                    },
                    campaign_id=settings.CAMPAIGN_IDS_BY_EMAIL_TYPE[OfferUsageEmailTypes.DIGEST]
                ),
                mock.call(
                    {'example_1@example.com': 44, ' example_2@example.com': 44},
                    'Offer Usage Notification',
                    {
                        'email_type': OfferUsageEmailTypes.DIGEST, 'is_enrollment_limit_offer': True,
                        'percent_usage': 0, 'total_limit_str': 10, 'total_limit': 10,
                        'offer_type': 'Enrollment', 'offer_name': offer_with_daily_frequency.name, 'current_usage': 0,
                        'current_usage_str': 0,
                        'remaining_balance': 10, 'remaining_balance_str': '10',
                        'enterprise_customer_name': offer_with_daily_frequency.condition.enterprise_customer_name,
                    },
                    campaign_id=settings.CAMPAIGN_IDS_BY_EMAIL_TYPE[OfferUsageEmailTypes.DIGEST]
                ),
                mock.call(
                    {'example_1@example.com': 44, ' example_2@example.com': 44},
                    'Offer Usage Notification',
                    {
                        'email_type': OfferUsageEmailTypes.DIGEST, 'is_enrollment_limit_offer': True,
                        'percent_usage': 0, 'total_limit_str': 10, 'total_limit': 10,
                        'offer_type': 'Enrollment', 'offer_name': offer_with_weekly_frequency.name, 'current_usage': 0,
                        'current_usage_str': 0,
                        'remaining_balance': 10, 'remaining_balance_str': '10',
                        'enterprise_customer_name': offer_with_weekly_frequency.condition.enterprise_customer_name,
                    },
                    campaign_id=settings.CAMPAIGN_IDS_BY_EMAIL_TYPE[OfferUsageEmailTypes.DIGEST]
                ),
                mock.call(
                    {'example_1@example.com': 44, ' example_2@example.com': 44},
                    'Offer Usage Notification',
                    {
                        'email_type': OfferUsageEmailTypes.DIGEST, 'is_enrollment_limit_offer': True,
                        'percent_usage': 0, 'total_limit_str': 10, 'total_limit': 10, 'offer_type': 'Enrollment',
                        'offer_name': offer_with_monthly_frequency.name,
                        'current_usage': 0, 'current_usage_str': 0,
                        'remaining_balance': 10, 'remaining_balance_str': '10',
                        'enterprise_customer_name': offer_with_monthly_frequency.condition.enterprise_customer_name,
                    },
                    campaign_id=settings.CAMPAIGN_IDS_BY_EMAIL_TYPE[OfferUsageEmailTypes.DIGEST]
                ),
            ])

    @responses.activate
    def test_command_force_digest_single_enterprise(self):
        """
        Test the send_api_triggered_offer_emails command on a single enterprise customer, forcing
        it to send the digest email.
        """

        offer_1 = EnterpriseOfferFactory(max_discount=100)
        offer_usage_count = OfferUsageEmail.objects.all().count()
        admin_email_1, admin_email_2 = 'example_1@example.com', 'example_2@example.com'
        self.mock_lms_user_responses({
            admin_email_1: 22,
            admin_email_2: 44,
        })

        customer_uuid = offer_1.condition.enterprise_customer_uuid
        self.mock_offer_analytics_response(customer_uuid, offer_1.id)

        with mock.patch(API_TRIGGERED_PATH + '.send_api_triggered_offer_usage_email.delay') as mock_send_email:
            mock_send_email.return_value = mock.Mock()
            call_command(
                'send_api_triggered_offer_emails',
                enterprise_customer_uuid=customer_uuid,
                force_type=OfferUsageEmailTypes.DIGEST,
            )
            assert mock_send_email.call_count == 1
            assert OfferUsageEmail.objects.all().count() == offer_usage_count + 1

            mock_send_email.assert_has_calls([
                mock.call(
                    {'example_1@example.com': 22, ' example_2@example.com': 44},
                    'Offer Usage Notification',
                    {
                        'email_type': OfferUsageEmailTypes.DIGEST, 'is_enrollment_limit_offer': False,
                        'percent_usage': 50.0, 'total_limit': 10000.0, 'total_limit_str': '$10,000.00',
                        'offer_type': 'Booking', 'offer_name': offer_1.name, 'current_usage': 5000.0,
                        'current_usage_str': '$5,000.00',
                        'remaining_balance': 5000.0, 'remaining_balance_str': '$5,000.00',
                        'enterprise_customer_name': offer_1.condition.enterprise_customer_name,
                    },
                    campaign_id=settings.CAMPAIGN_IDS_BY_EMAIL_TYPE[OfferUsageEmailTypes.DIGEST]
                ),
            ])

    def test_deprecated_command(self):
        """
        Test the deprecated version of the command.
        """
        ConditionalOffer.objects.all().delete()
        OfferUsageEmail.objects.all().delete()

        EnterpriseOfferFactory(max_discount=100)

        with mock.patch(DEPRECATED_PATH + '.send_offer_usage_email.delay') as mock_send_email:
            with LogCapture(level=logging.INFO) as log:
                mock_send_email.return_value = mock.Mock()
                call_command('send_enterprise_offer_limit_emails')
                assert mock_send_email.call_count == 1
                assert OfferUsageEmail.objects.all().count() == 1
        log.check_present(
            (
                DEPRECATED_PATH,
                'INFO',
                '[Offer Usage Alert] Total count of enterprise offers is {total_enterprise_offers_count}.'.format(
                    total_enterprise_offers_count=1
                )
            ),
            (
                DEPRECATED_PATH,
                'INFO',
                '[Offer Usage Alert] {total_enterprise_offers_count} of {send_enterprise_offer_count} added to the'
                ' email sending queue.'.format(
                    total_enterprise_offers_count=1,
                    send_enterprise_offer_count=1,
                )
            )
        )
