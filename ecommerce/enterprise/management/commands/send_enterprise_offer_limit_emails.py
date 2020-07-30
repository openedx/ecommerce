"""
Send the enterprise offer limits emails.
"""
import logging
from datetime import datetime

from django.core.management import BaseCommand
from django.db.models import Sum
from ecommerce_worker.sailthru.v1.tasks import send_offer_usage_email

from ecommerce.extensions.fulfillment.status import ORDER
from ecommerce.programs.custom import get_model

ConditionalOffer = get_model('offer', 'ConditionalOffer')
OfferUsageEmail = get_model('offer', 'OfferUsageEmail')
OrderDiscount = get_model('order', 'OrderDiscount')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

EMAIL_BODY = """
    You have used {percentage_usage}% of the {offer_type} Limit associated with the entitlement offer called
     "{offer_name}"\n {offer_type}s Redeemed: {current_usage}\n {offer_type}s Limit: {total_limit}\n Please reach out to
     customersuccess@edx.org, or to your Account Manager or Customer Success representative, if you have any questions.
    """
EMAIL_SUBJECT = "Offer Usage Notification"


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
            is_eligible = True
        elif enterprise_offer.usage_email_frequency == ConditionalOffer.WEEKLY:
            is_eligible = diff_of_days >= 7
        else:
            is_eligible = diff_of_days >= 30
        return is_eligible

    @staticmethod
    def get_enrollment_limits(offer):
        """
        Return the percentage usage and total limit of enrollment limit.
        """
        return (offer.num_orders / offer.max_global_applications) * 100, offer.num_orders

    @staticmethod
    def get_booking_limits(offer):
        """
        Return the percentage usage and total limit of booking limit.
        """
        total_used_discount_amount = OrderDiscount.objects.filter(
            offer_id=offer.id,
            order__status=ORDER.COMPLETE
        ).aggregate(Sum('amount'))['amount__sum']
        total_used_discount_amount = total_used_discount_amount if total_used_discount_amount else 0
        return (total_used_discount_amount / offer.max_discount) * 100, total_used_discount_amount

    def get_email_content(self, offer):
        """
        Return the appropriate email body and subject of given offer.
        """
        is_enrollment_limit_offer = bool(offer.max_global_applications)
        percentage_usage, current_usage = self.get_enrollment_limits(offer) if is_enrollment_limit_offer \
            else self.get_booking_limits(offer)

        email_body = EMAIL_BODY.format(
            percentage_usage=int(percentage_usage),
            total_limit=offer.max_global_applications if is_enrollment_limit_offer else offer.max_discount,
            offer_type='Enrollment' if is_enrollment_limit_offer else 'Booking',
            offer_name=offer.name,
            current_usage=int(current_usage)
        )
        return email_body, EMAIL_SUBJECT

    @staticmethod
    def _get_enterprise_offers():
        """
        Return the enterprise offers which have opted for email usage alert.
        """
        return ConditionalOffer.objects.filter(
            emails_for_usage_alert__isnull=False,
            condition__enterprise_customer_uuid__isnull=False
        )

    def handle(self, *args, **options):
        send_enterprise_offer_count = 0
        enterprise_offers = self._get_enterprise_offers()
        total_enterprise_offers_count = enterprise_offers.count()
        logger.info('[Offer Usage Alert] Total count of enterprise offers is %s.', total_enterprise_offers_count)
        for enterprise_offer in enterprise_offers:
            if self.is_eligible_for_alert(enterprise_offer):
                logger.info('[Offer Usage Alert] Sending email for offer %s', enterprise_offer.name)
                send_enterprise_offer_count += 1
                email_body, email_subject = self.get_email_content(enterprise_offer)
                send_offer_usage_email.delay(enterprise_offer.emails_for_usage_alert, email_subject, email_body)
        logger.info(
            '[Offer Usage Alert] %s of %s added to the email sending queue.',
            total_enterprise_offers_count,
            send_enterprise_offer_count
        )
