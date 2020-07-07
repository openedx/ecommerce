"""
Send the enterprise offer limits emails.
"""


import logging

from django.core.management import BaseCommand

from ecommerce_worker.sailthru.v1.tasks import send_offer_update_email
from ecommerce.programs.custom import get_model

ConditionalOffer = get_model('offer', 'ConditionalOffer')
Product = get_model('catalogue', 'Product')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Command(BaseCommand):
    """
    Send the enterprise offer limits emails.
    """

    @staticmethod
    def _get_enterprise_offers():
        """
        Return the enterprise offer which have enabled for email usage alert.
        """
        return ConditionalOffer.objects.filter(
            offer_type=ConditionalOffer.SITE,
            emails_for_offer_usage_alert__isnull=False,
            condition__enterprise_customer_uuid__isnull=False
        )

    @staticmethod
    def get_email_body(enterprise_offer):
        email_body = 'You have used {percentage_usage} of the {offer_type} associated with the entitlement offer ' \
                     'called {offer_name}\n Bookings Redeemed: {booking_redeemed}\n Bookings Limit: {booking_limit}\n' \
                     'Enrollments Redeemed: {enrollment_redeemed}\n Enrollments Limit: {enrollment_limit}\n'\
                     'Please reach out to customersuccess@edx.org, or to your Account Manager or Customer Success ' \
                     'representative, if you have any questions.'
        return email_body

    def get_email_content(self, enterprise_offer):
        email_subject = 'Offer Usage Notification'
        email_body = self.get_email_body(enterprise_offer)
        return email_subject, email_body

    @staticmethod
    def convert_comma_separated_string_to_list(comma_separated_string):
        """
        Convert the comma separated string to a valid list.
        """
        return list(set(item.strip() for item in comma_separated_string.split(",") if item.strip()))

    def handle(self, *args, **options):
        enterprise_offers = self._get_enterprise_offers()
        for enterprise_offer in enterprise_offers:
            email_list = self.convert_comma_separated_string_to_list(enterprise_offer.emails_for_offer_usage_alert)
            email_subject, email_body = self.get_email_content(enterprise_offer)
            for email in email_list:
                send_offer_update_email.delay(email, email_subject, email_body)

