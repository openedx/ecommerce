"""
This command updates the subject of nudge email templates.
"""

import logging

from django.core.management import BaseCommand
from oscar.core.loading import get_model

from ecommerce.extensions.offer.constants import DAY19

CodeAssignmentNudgeEmailTemplates = get_model('offer', 'CodeAssignmentNudgeEmailTemplates')


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Update the subject line of nudge email template for Day 19.

    Example:

        ./manage.py update_nudge_email_subject
    """

    help = "Fix subject line of nudge email template for Day 19"

    def handle(self, *args, **options):
        email_template = CodeAssignmentNudgeEmailTemplates.objects.get(email_type=DAY19)
        email_template.email_subject = "It's not too late to redeem your edX code!"

        email_template.save()

        logger.info("Successfully Updated the subject line of nudge email template for Day 19.")
