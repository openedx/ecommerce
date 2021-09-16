"""
Send the enterprise code assignment nudge emails.
"""
import logging
from datetime import datetime

from django.contrib.sites.models import Site
from django.core.management import BaseCommand
from django.utils import timezone
from ecommerce_worker.email.v1.api import send_code_assignment_nudge_email

from ecommerce.core.models import User
from ecommerce.enterprise.utils import (
    get_enterprise_customer_reply_to_email,
    get_enterprise_customer_sender_alias,
    get_enterprise_customer_uuid
)
from ecommerce.extensions.offer.constants import AUTOMATIC_EMAIL
from ecommerce.extensions.voucher.utils import get_cached_voucher
from ecommerce.programs.custom import get_model

CodeAssignmentNudgeEmails = get_model('offer', 'CodeAssignmentNudgeEmails')
CodeAssignmentNudgeEmailTemplates = get_model('offer', 'CodeAssignmentNudgeEmailTemplates')
OfferAssignment = get_model('offer', 'OfferAssignment')
OfferAssignmentEmailSentRecord = get_model('offer', 'OfferAssignmentEmailSentRecord')
Voucher = get_model('voucher', 'Voucher')

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

    @staticmethod
    def _create_email_sent_record(site, nudge_email):
        """
        Creates an instance of OfferAssignmentEmailSentRecord with the given data.
        Arguments:
            nudge_email (CodeAssignmentNudgeEmails): A nudge email sent to the learner.
        """
        OfferAssignmentEmailSentRecord.create_email_record(
            enterprise_customer_uuid=get_enterprise_customer_uuid(nudge_email.code),
            email_type=nudge_email.email_template.email_type,
            template=nudge_email.email_template,
            sender_category=AUTOMATIC_EMAIL,
            code=nudge_email.code,
            user_email=nudge_email.user_email,
            receiver_id=User.get_lms_user_attribute_using_email(site, nudge_email.user_email)
        )

    @staticmethod
    def _get_sender_alias(site, nudge_email):
        """
        Returns the sender alias of an Enterprise Customer.

        Arguments:
            nudge_email (CodeAssignmentNudgeEmails): A nudge email sent to the learner.
        """
        enterprise_customer_uuid = get_enterprise_customer_uuid(nudge_email.code)
        return get_enterprise_customer_sender_alias(site, enterprise_customer_uuid)

    @staticmethod
    def _get_reply_to_email(site, nudge_email):
        """
        Returns the reply_to email address of an Enterprise Customer.

        Arguments:
            nudge_email (CodeAssignmentNudgeEmails): A nudge email sent to the learner.
        """
        enterprise_customer_uuid = get_enterprise_customer_uuid(nudge_email.code)
        return get_enterprise_customer_reply_to_email(site, enterprise_customer_uuid)

    def handle(self, *args, **options):
        send_nudge_email_count = 0
        site = Site.objects.get_current()
        nudge_emails = self._get_nudge_emails()
        total_nudge_emails_count = nudge_emails.count()
        logger.info(
            '[Code Assignment Nudge Email] Total count of Enterprise Nudge Emails that are scheduled for today is %s.',
            total_nudge_emails_count
        )
        for nudge_email in nudge_emails:
            try:
                voucher = get_cached_voucher(nudge_email.code)
            except Voucher.DoesNotExist:
                continue
            if voucher.is_expired():
                # unsubscribe the user to avoid sending any nudge in future regarding this same code assignment
                CodeAssignmentNudgeEmails.unsubscribe_from_nudging(
                    codes=[nudge_email.code],
                    user_emails=[nudge_email.user_email]
                )
                continue

            base_enterprise_url = nudge_email.options.get('base_enterprise_url', '')
            # Get the formatted email body and subject on the bases of given code.
            email_body, email_subject = nudge_email.email_template.get_email_content(
                nudge_email.user_email,
                nudge_email.code,
                base_enterprise_url=base_enterprise_url,
            )
            if email_body:
                nudge_email.already_sent = True
                nudge_email.save()
                send_nudge_email_count += 1
                sender_alias = self._get_sender_alias(site, nudge_email)
                reply_to = self._get_reply_to_email(site, nudge_email)
                send_code_assignment_nudge_email.delay(
                    nudge_email.user_email,
                    email_subject,
                    email_body,
                    sender_alias,
                    reply_to,
                    base_enterprise_url=base_enterprise_url,
                )
                self.set_last_reminder_date(nudge_email.user_email, nudge_email.code)
                self._create_email_sent_record(site, nudge_email)
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
