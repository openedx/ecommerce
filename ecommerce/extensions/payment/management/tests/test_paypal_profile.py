

import json
from io import StringIO

import ddt
import mock
from django.core.management import call_command
from django.core.management.base import CommandError

from ecommerce.extensions.payment.models import PaypalWebProfile
from ecommerce.tests.testcases import TestCase


@ddt.ddt
@mock.patch('ecommerce.extensions.payment.management.commands.paypal_profile.WebProfile')
class TestPaypalProfileCommand(TestCase):
    TEST_ID = 'test-id'
    TEST_JSON = '{"test": "json"}'
    TEST_NAME = 'test-name'
    PAYMENT_PROCESSOR_CONFIG_KEY = 'edX'

    def setUp(self):
        self.stdout = StringIO()
        self.assertEqual(PaypalWebProfile.objects.count(), 0)

        self.mock_profile_instance = mock.Mock()
        self.mock_profile_instance.create.return_value = True
        self.mock_profile_instance.update.return_value = True
        self.mock_profile_instance.delete.return_value = True
        self.mock_profile_instance.id = self.TEST_ID
        self.mock_profile_instance.name = self.TEST_NAME
        self.mock_profile_instance.to_dict.return_value = json.loads(self.TEST_JSON)

    def check_stdout(self, expected_json):
        raw_stdout = self.stdout.getvalue().strip()
        actual_value = json.loads(raw_stdout)
        expected_value = json.loads(expected_json)
        self.assertEqual(actual_value, expected_value)

    def check_enabled(self, is_enabled=True):
        try:
            PaypalWebProfile.objects.get(id=self.TEST_ID, name=self.TEST_NAME)
            self.assertTrue(is_enabled)
        except PaypalWebProfile.DoesNotExist:
            self.assertFalse(is_enabled)

    def call_command_action(self, action, test_id=None, test_json=None, **options):
        call_command('paypal_profile',
                     partner=self.PAYMENT_PROCESSOR_CONFIG_KEY,
                     action=action,
                     profile_id=test_id,
                     json=test_json,
                     stdout=self.stdout,
                     **options)

    def test_list(self, mock_profile):
        mock_profile.all.return_value = [self.mock_profile_instance]
        self.call_command_action("list")
        self.assertTrue(mock_profile.all.called)
        self.check_stdout('[{}]'.format(self.TEST_JSON))

    def test_create(self, mock_profile):
        mock_profile.return_value = self.mock_profile_instance
        self.call_command_action("create", test_json=self.TEST_JSON)
        self.assertTrue(mock_profile.called)
        self.assertEqual(mock_profile.call_args[0][0], json.loads(self.TEST_JSON))
        self.assertTrue(self.mock_profile_instance.create.called)
        self.check_stdout(self.TEST_JSON)

    def test_show(self, mock_profile):
        mock_profile.find.return_value = self.mock_profile_instance
        self.call_command_action("show", test_id=self.TEST_ID)
        self.assertTrue(mock_profile.find.called)
        self.assertEqual(mock_profile.find.call_args[0][0], self.TEST_ID)
        self.check_stdout(self.TEST_JSON)

    def test_update(self, mock_profile):
        mock_profile.find.return_value = self.mock_profile_instance
        self.call_command_action("update", test_id=self.TEST_ID, test_json=self.TEST_JSON)
        self.assertTrue(self.mock_profile_instance.update.called)
        self.assertEqual(self.mock_profile_instance.update.call_args[0][0], json.loads(self.TEST_JSON))
        self.check_stdout(self.TEST_JSON)

    @ddt.data(True, False)
    def test_delete(self, is_enabled, mock_profile):
        mock_profile.find.return_value = self.mock_profile_instance
        if is_enabled:
            PaypalWebProfile.objects.create(id=self.TEST_ID, name=self.TEST_NAME)
        try:
            self.call_command_action("delete", test_id=self.TEST_ID)
            self.assertTrue(self.mock_profile_instance.delete.called)
            self.check_stdout(self.TEST_JSON)
            self.assertFalse(is_enabled)
        except CommandError:
            self.assertTrue(is_enabled)

    def test_enable(self, mock_profile):
        mock_profile.find.return_value = self.mock_profile_instance
        self.call_command_action("enable", test_id=self.TEST_ID)
        self.check_enabled()
        # test idempotency
        self.call_command_action("enable", test_id=self.TEST_ID)
        self.check_enabled()

    def test_disable(self, mock_profile):  # pylint: disable=unused-argument
        PaypalWebProfile.objects.create(id=self.TEST_ID, name=self.TEST_NAME)
        self.call_command_action("disable", test_id=self.TEST_ID)
        self.check_enabled(False)
        # test idempotency
        self.call_command_action("disable", test_id=self.TEST_ID)
        self.check_enabled(False)

    def test_missing_required_parameters(self, mock_profile):  # pylint: disable=unused-argument
        """
        Tests that command raises Command Error if required parameters are missing
        """
        # pylint: disable=protected-access

        with self.assertRaises(CommandError) as context:
            call_command('paypal_profile', stdout=self.stdout)  # no config and action
        self.assertEqual('Required arguments `partner` and `action` are missing', str(context.exception))

        with self.assertRaises(CommandError) as context:
            call_command('paypal_profile', partner='edX', stdout=self.stdout)  # no action
        self.assertEqual('Required arguments `partner` and `action` are missing', str(context.exception))

        with self.assertRaises(CommandError) as context:
            call_command('paypal_profile', partner='no_paypal', action='list', stdout=self.stdout)  # unknown profile
        self.assertEqual(
            'Payment Processor configuration for partner `no_paypal` does not contain PayPal settings',
            str(context.exception))

        with self.assertRaises(CommandError) as context:
            call_command('paypal_profile', partner='edX', action='create', stdout=self.stdout)  # no json
        self.assertEqual('Action `create` requires a JSON string to be specified.', str(context.exception))

        with self.assertRaises(CommandError) as context:
            call_command('paypal_profile', partner='edX', action='show', stdout=self.stdout)  # no profile id
        self.assertEqual('Action `show` requires a profile_id to be specified.', str(context.exception))

        with self.assertRaises(CommandError) as context:
            call_command('paypal_profile', partner='edX', action='update', stdout=self.stdout)  # no profile id
        self.assertEqual('Action `update` requires a profile_id to be specified.', str(context.exception))

        with self.assertRaises(CommandError) as context:
            call_command('paypal_profile', partner='edX', action='update', profile_id=self.TEST_ID,
                         stdout=self.stdout)  # no json
        self.assertEqual('Action `update` requires a JSON string to be specified.', str(context.exception))

        with self.assertRaises(CommandError) as context:
            call_command('paypal_profile', partner='edX', action='delete', stdout=self.stdout)  # no profile id
        self.assertEqual('Action `delete` requires a profile_id to be specified.', str(context.exception))

        with self.assertRaises(CommandError) as context:
            call_command('paypal_profile', partner='edX', action='enable', stdout=self.stdout)  # no profile id
        self.assertEqual('Action `enable` requires a profile_id to be specified.', str(context.exception))

        with self.assertRaises(CommandError) as context:
            call_command('paypal_profile', partner='edX', action='disable', stdout=self.stdout)  # no profile id
        self.assertEqual('Action `disable` requires a profile_id to be specified.', str(context.exception))
