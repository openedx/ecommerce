# encoding: utf-8
"""
Contains the tests for sending the enterprise code assignment nudge emails command.
"""
import datetime
import logging

import mock
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
        voucher = VoucherFactory()
        voucher.offers.add(EnterpriseOfferFactory(max_global_applications=98))

        self.total_nudge_emails_for_today = 5
        self.nudge_emails = CodeAssignmentNudgeEmailsFactory.create_batch(
            self.total_nudge_emails_for_today, code=voucher.code
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
        with mock.patch('ecommerce_worker.sailthru.v1.tasks.send_code_assignment_nudge_email.delay') as mock_send_email:
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
        nudge_email_without_voucher = CodeAssignmentNudgeEmailsFactory(code=code)
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
                MODEL_LOGGER_NAME,
                'WARNING',
                '[Code Assignment Nudge Email] Unable to send the email for user_email: {user_email}, code: '
                '{code} because code does not have associated voucher.'.format(
                    user_email=nudge_email_without_voucher.user_email,
                    code=code
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
