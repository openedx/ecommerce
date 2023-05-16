"""
Send the enterprise offer limits emails.
"""
import logging
from datetime import datetime
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import BaseCommand
from ecommerce_worker.email.v1.api import send_api_triggered_offer_usage_email
from requests.exceptions import RequestException

from ecommerce.core.models import User
from ecommerce.extensions.offer.constants import OfferUsageEmailTypes
from ecommerce.programs.custom import get_model

ConditionalOffer = get_model('offer', 'ConditionalOffer')
OfferUsageEmail = get_model('offer', 'OfferUsageEmail')
OrderDiscount = get_model('order', 'OrderDiscount')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

EMAIL_SUBJECT = 'Offer Usage Notification'

# Reasons why an email should not be sent
THRESHOLD_NOT_REACHED = 'Threshold not reached.'
EMAIL_SENT_BEFORE_OFFER_NOT_REPLENISHED = 'Email sent before, offer has not been replenished.'


class Command(BaseCommand):
    """
    Send the enterprise offer limits emails.
    """

    @staticmethod
    def get_enrollment_limits(offer):
        """
        Return the total limit, percentage usage and current usage of enrollment limit.
        """
        percentage_usage = int((offer.num_orders / offer.max_global_applications) * 100)
        remaining_balance = offer.max_global_applications - offer.num_orders
        return {
            'total_limit': int(offer.max_global_applications),
            'percentage_usage': percentage_usage,
            'current_usage': int(offer.num_orders),
            'remaining_balance': remaining_balance,
        }

    @staticmethod
    def get_booking_limits(site, offer):
        """
        Return the total discount limit, percentage usage and current usage of booking limit.
        """
        api_client = site.siteconfiguration.oauth_api_client
        enterprise_customer_uuid = offer.condition.enterprise_customer_uuid
        offer_analytics_url = urljoin(
            settings.ENTERPRISE_ANALYTICS_API_URL,
            f'/enterprise/api/v1/enterprise/{enterprise_customer_uuid}/offers/{offer.id}/',
        )
        response = api_client.get(offer_analytics_url)
        response.raise_for_status()
        offer_analytics = response.json()

        return {
            'total_limit': offer_analytics['max_discount'],
            'percentage_usage': offer_analytics['percent_of_offer_spent'] * 100,  # percent_of_offer_spent is 0-1
            'current_usage': offer_analytics['amount_of_offer_spent'],
            'remaining_balance': offer_analytics['remaining_balance'],
        }

    @staticmethod
    def is_eligible_for_email(enterprise_offer):
        """
        Return whether given offer is eligible for sending a usage email.
        """
        return enterprise_offer.max_global_applications or enterprise_offer.max_discount

    def should_send_email_type(self, enterprise_offer, email_type, total_limit):
        """
        Return whether an email of the given type should be sent for the offer.

        Evaluates to True if an email of the given type has not been sent before or if the offer has been re-upped.
        """
        last_email_of_type_sent = OfferUsageEmail.objects.filter(offer=enterprise_offer, email_type=email_type).last()

        if not last_email_of_type_sent:
            return True

        email_metadata = last_email_of_type_sent.offer_email_metadata

        # All emails sent after 6/28/22 should have this field in the metadata
        previous_usage_data = email_metadata.get('email_usage_data')
        if not previous_usage_data:
            return True

        # Offer limit has been increased, we can send emails again
        previous_total_limit = previous_usage_data['total_limit']
        if total_limit > previous_total_limit:
            return True

        return False

    def is_eligible_for_no_balance_email(self, enterprise_offer, usage_info, is_enrollment_limit_offer):
        """
        Return whether an offer is eligible for the out of balance email.
        """
        percentage_usage = usage_info['percentage_usage']
        total_limit = usage_info['total_limit']
        current_usage = usage_info['current_usage']

        should_send_email = self.should_send_email_type(
            enterprise_offer,
            OfferUsageEmailTypes.OUT_OF_BALANCE,
            total_limit
        )

        if not should_send_email:
            return (False, EMAIL_SENT_BEFORE_OFFER_NOT_REPLENISHED)

        if is_enrollment_limit_offer:
            return (percentage_usage == 100, THRESHOLD_NOT_REACHED)

        return (total_limit - current_usage <= 100, THRESHOLD_NOT_REACHED)

    def is_eligible_for_low_balance_email(
        self,
        enterprise_offer,
        usage_info,
    ):
        """
        Return whether an offer is eligible for the low balance email.
        """
        percentage_usage = usage_info['percentage_usage']
        total_limit = usage_info['total_limit']

        return percentage_usage >= 75 and self.should_send_email_type(
            enterprise_offer, OfferUsageEmailTypes.LOW_BALANCE, total_limit
        )

    def is_eligible_for_digest_email(self, enterprise_offer):
        """
        Return whether given offer is eligible for the digest email.
        """
        last_digest_email = OfferUsageEmail.objects.filter(
            offer=enterprise_offer,
            email_type=OfferUsageEmailTypes.DIGEST
        ).last()

        diff_of_days = datetime.now().toordinal() - (last_digest_email.created.toordinal() if last_digest_email else 0)

        if enterprise_offer.usage_email_frequency == ConditionalOffer.DAILY:
            return diff_of_days >= 1

        if enterprise_offer.usage_email_frequency == ConditionalOffer.WEEKLY:
            return diff_of_days >= 7

        return diff_of_days >= 30

    def get_email_type(
        self,
        enterprise_offer,
        usage_info,
        is_enrollment_limit_offer,
    ):
        """
        Return the type of email that should be sent for the offer.

        Evaluates to None if an email should not be sent.
        """
        eligible_for_no_balance_email, ineligible_for_no_balance_email_reason = self.is_eligible_for_no_balance_email(
            enterprise_offer, usage_info, is_enrollment_limit_offer
        )

        if eligible_for_no_balance_email:
            return OfferUsageEmailTypes.OUT_OF_BALANCE

        # Don't send low balance email or digest email until offer has been reupped
        if ineligible_for_no_balance_email_reason == EMAIL_SENT_BEFORE_OFFER_NOT_REPLENISHED:
            return None

        if self.is_eligible_for_low_balance_email(enterprise_offer, usage_info):
            return OfferUsageEmailTypes.LOW_BALANCE

        if self.is_eligible_for_digest_email(enterprise_offer):
            return OfferUsageEmailTypes.DIGEST

        return None

    def get_email_content(self, site, offer):
        """
        Return the appropriate email body and subject of given offer.
        """
        is_enrollment_limit_offer = bool(offer.max_global_applications)

        usage_info = (
            self.get_enrollment_limits(offer)
            if is_enrollment_limit_offer
            else self.get_booking_limits(site, offer)
        )

        money_template = '${:,.2f}'
        total_limit = usage_info['total_limit']
        percentage_usage = usage_info['percentage_usage']
        current_usage = usage_info['current_usage']
        remaining_balance = usage_info['remaining_balance']
        remaining_balance_str = (
            str(remaining_balance)
            if is_enrollment_limit_offer
            else money_template.format(remaining_balance)
        )

        email_type = self.get_email_type(offer, usage_info, is_enrollment_limit_offer)

        return {
            'email_type': email_type,
            'percent_usage': percentage_usage,
            'is_enrollment_limit_offer': is_enrollment_limit_offer,
            'total_limit': total_limit,
            'total_limit_str': total_limit if is_enrollment_limit_offer else money_template.format(total_limit),
            'offer_type': 'Enrollment' if is_enrollment_limit_offer else 'Booking',
            'offer_name': offer.name,
            'current_usage': current_usage,
            'current_usage_str': current_usage if is_enrollment_limit_offer else money_template.format(current_usage),
            'remaining_balance': remaining_balance,
            'remaining_balance_str': remaining_balance_str,
            'enterprise_customer_name': offer.condition.enterprise_customer_name,
        }

    @staticmethod
    def _get_enterprise_offers(enterprise_customer_uuid=None):
        """
        Return the enterprise offers which have opted for email usage alert.
        """
        filter_kwargs = {
            'emails_for_usage_alert__isnull': False,
            'condition__enterprise_customer_uuid__isnull': False,
        }

        if enterprise_customer_uuid:
            filter_kwargs['condition__enterprise_customer_uuid'] = enterprise_customer_uuid

        return ConditionalOffer.objects.filter(**filter_kwargs).exclude(emails_for_usage_alert='')

    def add_arguments(self, parser):
        parser.add_argument(
            '--enterprise-customer-uuid',
            default=None,
            help="Run command only for the given Customer's Offers",
        )
        parser.add_argument(
            '--force-type',
            dest='force_type',
            choices=[
                OfferUsageEmailTypes.DIGEST,
                OfferUsageEmailTypes.LOW_BALANCE,
                OfferUsageEmailTypes.OUT_OF_BALANCE,
            ],
            help="Send the specified email type to recipients, regardless of the last OfferUsageRecord for the offer.",
        )

    def handle(self, *args, **options):
        successful_send_count = 0
        enterprise_offers = self._get_enterprise_offers(options['enterprise_customer_uuid'])
        total_enterprise_offers_count = enterprise_offers.count()
        logger.info('[Offer Usage Alert] Total count of enterprise offers is %s.', total_enterprise_offers_count)

        force_type = options['force_type']
        if options['force_type']:
            logger.info('Force sending a %s email for each of these offers', force_type)

        for enterprise_offer in enterprise_offers:
            if force_type or self.is_eligible_for_email(enterprise_offer):
                site = Site.objects.get_current()

                try:
                    email_body_variables = self.get_email_content(
                        site,
                        enterprise_offer,
                    )
                except RequestException as exc:
                    logger.warning(
                        'Exception getting offer email content for offer %s. Exception: %s',
                        enterprise_offer.id,
                        exc,
                    )
                    continue

                email_type = force_type or email_body_variables['email_type']

                if email_type is None:
                    continue

                logger.info(
                    '[Offer Usage Alert] Sending %s email for Offer with Name %s, ID %s',
                    email_type,
                    enterprise_offer.name,
                    enterprise_offer.id
                )

                lms_user_ids_by_email = {
                    user_email: User.get_lms_user_attribute_using_email(site, user_email, attribute='id')
                    for user_email in enterprise_offer.emails_for_usage_alert.strip().split(',')
                }

                send_api_triggered_offer_usage_email.delay(
                    lms_user_ids_by_email,
                    EMAIL_SUBJECT,
                    email_body_variables,
                    campaign_id=settings.CAMPAIGN_IDS_BY_EMAIL_TYPE[email_type]
                )
                # We can't block until the task is done, because no celery backend
                # is configured for ecommerce/ecommerce-worker.  So there
                # may be instances where an OfferUsageEmail record exists,
                # but no email was really successfully sent.
                successful_send_count += 1
                OfferUsageEmail.create_record(
                    email_type=email_type,
                    offer=enterprise_offer,
                    meta_data={
                        'email_usage_data': email_body_variables,
                        'email_subject': EMAIL_SUBJECT,
                        'email_addresses': enterprise_offer.emails_for_usage_alert,
                    },
                )
        logger.info(
            '[Offer Usage Alert] %s of %s offers with usage alerts configured had an email sent.',
            successful_send_count,
            total_enterprise_offers_count,
        )
