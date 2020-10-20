"""
Send the enterprise code assignment nudge emails.
"""
import logging
from datetime import datetime

from django.core.management import BaseCommand
from ecommerce_worker.sailthru.v1.tasks import send_offer_usage_email

from ecommerce.programs.custom import get_model

CodeAssignmentNudgeEmails = get_model('offer', 'CodeAssignmentNudgeEmails')
CodeAssignmentNudgeEmailTemplates = get_model('offer', 'CodeAssignmentNudgeEmailTemplates')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Command(BaseCommand):
    """
    Send the code assignment nudge emails.
    """
    @staticmethod
    def _get_nudge_emails():
        """
        Return the CodeAssignmentNudgeEmails objects which are scheduled to be sent today.
        """
        return CodeAssignmentNudgeEmails.objects.filter(
            email_date__date=datetime.utcnow().date(),
            already_sent=False,
            is_subscribed=True
        )

    def handle(self, *args, **options):
        send_nudge_email_count = 0
        nudge_emails = self._get_nudge_emails()
        total_nudge_emails_count = nudge_emails.count()
        logger.info(
            '[Code Assignment Nudge Email] Total count of Enterprise Nudge Emails that are scheduled for today is %s.',
            total_nudge_emails_count
        )
        for nudge_email in nudge_emails:
            email_body, email_subject = nudge_email.email_template.get_email_content()
            nudge_email.already_sent = True
            nudge_email.save()
            send_nudge_email_count += 1
            send_offer_usage_email.delay(nudge_email.user_email, email_subject, email_body)
        logger.info(
            '[Code Assignment Nudge Email] %s of %s added to the email sending queue.',
            total_nudge_emails_count,
            send_nudge_email_count
        )


