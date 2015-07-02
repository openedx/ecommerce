from cStringIO import StringIO
import json

import ddt
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
import mock

from ecommerce.extensions.payment.management.commands.paypal_profile import Command as PaypalProfileCommand
from ecommerce.extensions.payment.models import PaypalWebProfile


@ddt.ddt
@mock.patch('ecommerce.extensions.payment.management.commands.paypal_profile.WebProfile')
class TestPaypalProfileCommand(TestCase):

    TEST_ID = 'test-id'
    TEST_JSON = '{"test": "json"}'
    TEST_NAME = 'test-name'

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

    def call_command_action(self, action, *args, **options):
        call_command('paypal_profile', action, *args, stdout=self.stdout, **options)

    def test_list(self, mock_profile):
        mock_profile.all.return_value = [self.mock_profile_instance]
        self.call_command_action("list")
        self.assertTrue(mock_profile.all.called)
        self.check_stdout('[{}]'.format(self.TEST_JSON))

    def test_create(self, mock_profile):
        mock_profile.return_value = self.mock_profile_instance
        self.call_command_action("create", self.TEST_JSON)
        self.assertTrue(mock_profile.called)
        self.assertEqual(mock_profile.call_args[0][0], json.loads(self.TEST_JSON))
        self.assertTrue(self.mock_profile_instance.create.called)
        self.check_stdout(self.TEST_JSON)

    def test_show(self, mock_profile):
        mock_profile.find.return_value = self.mock_profile_instance
        self.call_command_action("show", self.TEST_ID)
        self.assertTrue(mock_profile.find.called)
        self.assertEqual(mock_profile.find.call_args[0][0], self.TEST_ID)
        self.check_stdout(self.TEST_JSON)

    def test_update(self, mock_profile):
        mock_profile.find.return_value = self.mock_profile_instance
        self.call_command_action("update", self.TEST_ID, self.TEST_JSON)
        self.assertTrue(self.mock_profile_instance.update.called)
        self.assertEqual(self.mock_profile_instance.update.call_args[0][0], json.loads(self.TEST_JSON))
        self.check_stdout(self.TEST_JSON)

    @ddt.data(True, False)
    def test_delete(self, is_enabled, mock_profile):
        mock_profile.find.return_value = self.mock_profile_instance
        if is_enabled:
            PaypalWebProfile.objects.create(id=self.TEST_ID, name=self.TEST_NAME)
        try:
            self.call_command_action("delete", self.TEST_ID)
            self.assertTrue(self.mock_profile_instance.delete.called)
            self.check_stdout(self.TEST_JSON)
            self.assertFalse(is_enabled)
        except CommandError:
            self.assertTrue(is_enabled)

    def test_enable(self, mock_profile):
        mock_profile.find.return_value = self.mock_profile_instance
        self.call_command_action("enable", self.TEST_ID)
        self.check_enabled()
        # test idempotency
        self.call_command_action("enable", self.TEST_ID)
        self.check_enabled()

    def test_disable(self, mock_profile):  # pylint: disable=unused-argument
        PaypalWebProfile.objects.create(id=self.TEST_ID, name=self.TEST_NAME)
        self.call_command_action("disable", self.TEST_ID)
        self.check_enabled(False)
        # test idempotency
        self.call_command_action("disable", self.TEST_ID)
        self.check_enabled(False)

    def test_get_argument(self, mock_profile):  # pylint: disable=unused-argument
        # pylint: disable=protected-access
        args = ['foo']
        self.assertEqual('foo', PaypalProfileCommand._get_argument(args, 'dummy', 'dummy'))
        self.assertEqual(args, [])
        with self.assertRaises(CommandError) as exception:
            PaypalProfileCommand._get_argument(args, 'test-action', 'test-argument')
            self.assertEqual(exception.message, 'Action `test-action` requires a test-argument to be specified.')
