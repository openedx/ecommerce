# encoding: utf-8
"""
Contains the tests for sending the enterprise code assignment nudge emails command.
"""
import datetime
import logging

import mock
import pytz
from dateutil.relativedelta import relativedelta
from django.core.management import call_command
from django.utils import timezone
from testfixtures import LogCapture

from ecommerce.extensions.test.factories import (
    CodeAssignmentNudgeEmailsFactory,
    EnterpriseOfferFactory,
    OfferAssignmentFactory,
    VoucherFactory
)
from ecommerce.programs.custom import get_model
from ecommerce.tests.testcases import TestCase

CodeAssignmentNudgeEmails = get_model('offer', 'CodeAssignmentNudgeEmails')
OfferAssignment = get_model('offer', 'OfferAssignment')
OfferAssignmentEmailSentRecord = get_model('offer', 'OfferAssignmentEmailSentRecord')

LOGGER_NAME = 'ecommerce.enterprise.management.commands.send_code_assignment_nudge_emails'
MODEL_LOGGER_NAME = 'ecommerce.extensions.offer.models'


class SendCodeAssignmentNudgeEmailsTests(TestCase):
    """
    Tests the sending code assignment nudge emails command.
    """

    def setUp(self):
        """
        Setup the test data
        """
        super(SendCodeAssignmentNudgeEmailsTests, self).setUp()
        # Create a voucher with valid offer so we can get
        self.voucher = VoucherFactory()
        self.voucher.offers.add(EnterpriseOfferFactory(max_global_applications=98))

        self.total_nudge_emails_for_today = 5
        self.nudge_emails = CodeAssignmentNudgeEmailsFactory.create_batch(
            self.total_nudge_emails_for_today, code=self.voucher.code
        )
        CodeAssignmentNudgeEmailsFactory(
            email_date=datetime.datetime.now() + relativedelta(days=1)
        )
        CodeAssignmentNudgeEmailsFactory(
            email_date=datetime.datetime.now() + relativedelta(days=2)
        )

        for nudge_email in self.nudge_emails:
            OfferAssignmentFactory(code=nudge_email.code, user_email=nudge_email.user_email)

    def assert_last_reminder_date(self):
        current_date_time = timezone.now()
        for offer_assignment in OfferAssignment.objects.all():
            assert offer_assignment.last_reminder_date.date() == current_date_time.date()

    def _assert_sent_count(self):
        nudge_email = CodeAssignmentNudgeEmails.objects.all()
        assert nudge_email.filter(already_sent=True).count() == 0
        cmd_path = 'ecommerce.enterprise.management.commands.send_code_assignment_nudge_emails'
        with mock.patch(cmd_path + '.send_code_assignment_nudge_email.delay') as mock_send_email:
            with LogCapture(level=logging.INFO) as log:
                mock_send_email.return_value = mock.Mock()
                call_command('send_code_assignment_nudge_emails')
                assert mock_send_email.call_count == self.total_nudge_emails_for_today
                assert nudge_email.filter(already_sent=True).count() == self.total_nudge_emails_for_today
        return log

    def test_command(self):
        """
        Test the send_enterprise_offer_limit_emails command
        """
        log = self._assert_sent_count()
        self.assert_last_reminder_date()
        log.check_present(
            (
                LOGGER_NAME,
                'INFO',
                '[Code Assignment Nudge Email] Total count of Enterprise Nudge Emails that are scheduled for '
                'today is {send_nudge_email_count}.'.format(
                    send_nudge_email_count=self.total_nudge_emails_for_today
                )
            ),
            (
                LOGGER_NAME,
                'INFO',
                '[Code Assignment Nudge Email] {send_nudge_emails_count} out of {total_nudge_emails} added to the '
                'email sending queue.'.format(
                    total_nudge_emails=self.total_nudge_emails_for_today,
                    send_nudge_emails_count=self.total_nudge_emails_for_today
                )
            )
        )

    def test_nudge_email_command_with_invalid_code(self):
        """
        Test the send_enterprise_offer_limit_emails command
        """
        code = "dummy-code"
        CodeAssignmentNudgeEmailsFactory(code=code)
        log = self._assert_sent_count()
        log.check_present(
            (
                LOGGER_NAME,
                'INFO',
                '[Code Assignment Nudge Email] Total count of Enterprise Nudge Emails that are scheduled for '
                'today is {send_nudge_email_count}.'.format(
                    send_nudge_email_count=self.total_nudge_emails_for_today + 1
                )
            ),
            (
                LOGGER_NAME,
                'INFO',
                '[Code Assignment Nudge Email] {send_nudge_emails_count} out of {total_nudge_emails} added to the '
                'email sending queue.'.format(
                    total_nudge_emails=self.total_nudge_emails_for_today + 1,
                    send_nudge_emails_count=self.total_nudge_emails_for_today
                )
            )
        )

    def test_nudge_email_sent_record_created(self):
        """
        Test that an instance of OfferAssignmentEmailSentRecord is created when a nudge email is sent.
        """
        # Check that no email record exists yet
        assert OfferAssignmentEmailSentRecord.objects.count() == 0
        self._assert_sent_count()
        # Check that a new email record for every email has been created now that the nudge emails are sent
        assert OfferAssignmentEmailSentRecord.objects.count() == self.total_nudge_emails_for_today

    def test_nudge_email_with_expired_voucher(self):
        """
        Test that no nudge email is sent when voucher is expired and user is unsubscribed from receiving email.
        """
        self.voucher.end_datetime = datetime.datetime.now(pytz.UTC) - datetime.timedelta(days=1)
        self.voucher.save(update_fields=['end_datetime'])
        nudge_email = CodeAssignmentNudgeEmails.objects.all()
        cmd_path = 'ecommerce.enterprise.management.commands.send_code_assignment_nudge_emails'
        with mock.patch(cmd_path + '.send_code_assignment_nudge_email.delay') as mock_send_email:
            mock_send_email.return_value = mock.Mock()
            call_command('send_code_assignment_nudge_emails')
            # assert that no emails were sent
            assert mock_send_email.call_count == 0
            assert nudge_email.filter(already_sent=True).count() == 0
            # assert that nudge emails are unsubscribed if voucher is expired
            assert nudge_email.filter(is_subscribed=False).count() == self.total_nudge_emails_for_today
