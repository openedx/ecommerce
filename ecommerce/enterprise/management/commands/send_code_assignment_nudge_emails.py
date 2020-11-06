"""
Send the enterprise code assignment nudge emails.
"""
import logging
from datetime import datetime

from django.core.management import BaseCommand
from django.utils import timezone
from ecommerce_worker.sailthru.v1.tasks import send_code_assignment_nudge_email

from ecommerce.programs.custom import get_model

CodeAssignmentNudgeEmails = get_model('offer', 'CodeAssignmentNudgeEmails')
CodeAssignmentNudgeEmailTemplates = get_model('offer', 'CodeAssignmentNudgeEmailTemplates')
OfferAssignment = get_model('offer', 'OfferAssignment')

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
        # TODO: Removing this filter for testing purpose "email_date__date=datetime.now().date()"
        return CodeAssignmentNudgeEmails.objects.filter(
            email_date__date=datetime.now().date(),
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
            # Get the formatted email body and subject on the bases of given code.
            email_body, email_subject = nudge_email.email_template.get_email_content(
                nudge_email.user_email,
                nudge_email.code
            )
            if email_body:
                nudge_email.already_sent = True
                nudge_email.save()
                send_nudge_email_count += 1
                send_code_assignment_nudge_email.delay(nudge_email.user_email, email_subject, email_body)
                self.set_last_reminder_date(nudge_email.user_email, nudge_email.code)
        logger.info(
            '[Code Assignment Nudge Email] %s out of %s added to the email sending queue.',
            send_nudge_email_count,
            total_nudge_emails_count
        )

    @staticmethod
    def set_last_reminder_date(email, code):
        """
        Set reminder date for offer assignments with `email` and `code`.
        """
        current_date_time = timezone.now()
        OfferAssignment.objects.filter(code=code, user_email=email).update(last_reminder_date=current_date_time)
