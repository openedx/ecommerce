"""
Update offer Assignment Email Bounce Status.
"""
import logging
from datetime import datetime, timedelta

from django.core.management import BaseCommand
from ecommerce_worker.email.v1.api import did_email_bounce

from ecommerce.extensions.offer.constants import OFFER_ASSIGNED, OFFER_ASSIGNMENT_EMAIL_BOUNCED
from ecommerce.programs.custom import get_model

OfferAssignment = get_model('offer', 'OfferAssignment')
OfferAssignmentEmailSentRecord = get_model('offer', 'OfferAssignmentEmailSentRecord')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Command(BaseCommand):
    """
    Update bounce status for offer assignments.
    """
    help = ('This command runs periodically every day and updates '
            'offer assignment emails with their hard bounce status.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--site-code',
            action='store',
            dest='site_code',
            default=None,
            type=str,
            help='Short code for site specific configuration overrides.'
        )

        parser.add_argument(
            '--time-period',
            action='store',
            dest='time_period',
            default=12,
            help='Number of hours from now.',
            type=int,
        )

    @staticmethod
    def _get_offer_assignments_in_period(period):
        """
        Return the Offer Assignment Objects that have been created in the past period.

        Arguments:
            period (int): Number of hours in the past
        """
        time_threshold = datetime.now() - timedelta(hours=period)
        return OfferAssignment.objects.filter(
            created__gt=time_threshold,
            status=OFFER_ASSIGNED
        )

    @staticmethod
    def _update_email_bounce_status(offer_assignment):
        """
        Update the bounce status for the given offer assignment.

        Arguments:
            offer_assignment (OfferAssignment): Offer assignment object.
        """
        OfferAssignment.objects.filter(
            pk=offer_assignment.pk,
        ).update(status=OFFER_ASSIGNMENT_EMAIL_BOUNCED)

    def handle(self, *args, **options):
        """
        Entry point for management command execution.
        """
        time_period = options['time_period']
        site_code = options['site_code']

        offer_assignments = self._get_offer_assignments_in_period(time_period)
        for assignment in offer_assignments:
            if did_email_bounce(assignment.user_email, site_code=site_code):
                self._update_email_bounce_status(assignment)
