"""
Tests for Django management command to un-enroll refunded android users.
"""
from django.core.management import call_command
from mock import patch
from testfixtures import LogCapture

from ecommerce.tests.testcases import TestCase


class TestUnenrollRefundedAndroidUsersCommand(TestCase):

    LOGGER_NAME = 'ecommerce.core.management.commands.unenroll_refunded_android_users'

    @patch('requests.get')
    def test_handle_pass(self, mock_response):
        """ Test using mock response from setup, using threshold it will clear"""

        mock_response.return_value.status_code = 200

        with LogCapture(self.LOGGER_NAME) as log:
            call_command('unenroll_refunded_android_users')

            log.check(
                (
                    self.LOGGER_NAME,
                    'INFO',
                    'Sending request to un-enroll refunded android users'
                )
            )

    @patch('requests.get')
    def test_handle_fail(self, mock_response):
        """ Test using mock response from setup, using threshold it will clear"""

        mock_response.return_value.status_code = 400

        with LogCapture(self.LOGGER_NAME) as log:
            call_command('unenroll_refunded_android_users')

            log.check(
                (
                    self.LOGGER_NAME,
                    'INFO',
                    'Sending request to un-enroll refunded android users'
                ),
                (
                    self.LOGGER_NAME,
                    'ERROR',
                    'Failed to refund android users with status code 400'
                )
            )
