"""
Send the enterprise offer limits emails.
"""
import logging
from datetime import datetime
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management import BaseCommand
from ecommerce_worker.email.v1.api import send_offer_usage_email

from ecommerce.core.models import User
from ecommerce.programs.custom import get_model

ConditionalOffer = get_model('offer', 'ConditionalOffer')
OfferUsageEmail = get_model('offer', 'OfferUsageEmail')
OrderDiscount = get_model('order', 'OrderDiscount')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

EMAIL_SUBJECT = 'Offer Usage Notification'


class Command(BaseCommand):
    """
    Send the enterprise offer limits emails.
    """

    @staticmethod
    def is_eligible_for_alert(enterprise_offer):
        """
        Return the bool whether given offer is eligible for sending the email.
        """
        offer_usage = OfferUsageEmail.objects.filter(offer=enterprise_offer).last()
        diff_of_days = datetime.now().toordinal() - offer_usage.created.toordinal() if offer_usage else 0

        if not enterprise_offer.max_global_applications and not enterprise_offer.max_discount:
            is_eligible = False
        elif not offer_usage:
            is_eligible = True
        elif enterprise_offer.usage_email_frequency == ConditionalOffer.DAILY:
            is_eligible = diff_of_days >= 1
        elif enterprise_offer.usage_email_frequency == ConditionalOffer.WEEKLY:
            is_eligible = diff_of_days >= 7
        else:
            is_eligible = diff_of_days >= 30
        return is_eligible

    @staticmethod
    def get_enrollment_limits(offer):
        """
        Return the total limit, percentage usage and current usage of enrollment limit.
        """
        percentage_usage = int((offer.num_orders / offer.max_global_applications) * 100)
        return int(offer.max_global_applications), percentage_usage, int(offer.num_orders)

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
        if not offer_analytics:
            raise Exception(f'No analytics for offer: {offer.id}')

        return (
            offer_analytics['max_discount'],
            offer_analytics['percent_of_offer_spent'],
            offer_analytics['amount_of_offer_spent'],
        )

    def get_email_content(self, site, offer):
        """
        Return the appropriate email body and subject of given offer.
        """
        is_enrollment_limit_offer = bool(offer.max_global_applications)
        total_limit, percentage_usage, current_usage = (
            self.get_enrollment_limits(offer)
            if is_enrollment_limit_offer
            else self.get_booking_limits(site, offer)
        )

        return {
            'percent_usage': percentage_usage,
            'total_limit': total_limit if is_enrollment_limit_offer else "${}".format(total_limit),
            'offer_type': 'Enrollment' if is_enrollment_limit_offer else 'Booking',
            'offer_name': offer.name,
            'current_usage': current_usage if is_enrollment_limit_offer else "${}".format(current_usage),
        }

    @staticmethod
    def _get_enterprise_offers():
        """
        Return the enterprise offers which have opted for email usage alert.
        """
        return ConditionalOffer.objects.filter(
            emails_for_usage_alert__isnull=False,
            condition__enterprise_customer_uuid__isnull=False
        ).exclude(emails_for_usage_alert='')

    def handle(self, *args, **options):
        successful_send_count = 0
        enterprise_offers = self._get_enterprise_offers()
        total_enterprise_offers_count = enterprise_offers.count()
        logger.info('[Offer Usage Alert] Total count of enterprise offers is %s.', total_enterprise_offers_count)
        for enterprise_offer in enterprise_offers:
            if self.is_eligible_for_alert(enterprise_offer):
                logger.info(
                    '[Offer Usage Alert] Sending email for Offer with Name %s, ID %s',
                    enterprise_offer.name,
                    enterprise_offer.id
                )
                site = Site.objects.get_current()
                email_body = self.get_email_content(site, enterprise_offer)

                lms_user_ids_by_email = {
                    user_email: User.get_lms_user_attribute_using_email(site, user_email, attribute='id')
                    for user_email in enterprise_offer.emails_for_usage_alert.strip().split(',')
                }

                task_result = send_offer_usage_email.delay(
                    lms_user_ids_by_email,
                    EMAIL_SUBJECT,
                    email_body,
                )
                # Block until the task is done, since we're inside a management command
                # and likely running from a job scheduler (ex. Jenkins).
                # propagate=False means we won't re-raise (and exit this method) if any one task fails.
                task_result.get(propagate=False)
                if task_result.successful():
                    successful_send_count += 1
                    OfferUsageEmail.create_record(enterprise_offer, meta_data={
                        'email_body': email_body,
                        'email_subject': EMAIL_SUBJECT,
                        'email_addresses': enterprise_offer.emails_for_usage_alert
                    })
        logger.info(
            '[Offer Usage Alert] %s of %s offers with usage alerts configured had an email sent.',
            successful_send_count,
            total_enterprise_offers_count,
        )
