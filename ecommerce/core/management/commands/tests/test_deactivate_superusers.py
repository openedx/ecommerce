"""
Tests for Django management command to verify ecommerce transactions.
"""


import mock
from django.apps import apps
from django.core.management import call_command

from ecommerce.core.management.commands.tests.factories import SuperUserFactory
from ecommerce.tests.testcases import TestCase

User = apps.get_model('core', 'User')


class DeactivateSuperUsersTest(TestCase):
    command = 'deactivate_superusers'
    LOGGER = 'ecommerce.core.management.commands.deactivate_superusers.logger'

    def setUp(self):
        super(DeactivateSuperUsersTest, self).setUp()
        __ = SuperUserFactory()

    def _assert_superusers(self, expected_count):
        """Helper method which fetches superusers and verify their expected count"""
        super_users = User.objects.filter(is_superuser=True)
        self.assertEqual(super_users.count(), expected_count)

    def test_superuser_unset(self):
        """
        Test that deactivate superusers management command successfully marks
        superusers inactive.
        """
        self._assert_superusers(expected_count=1)
        with mock.patch(self.LOGGER) as patched_log:
            call_command(self.command)
            patched_log.info.assert_called_once_with('Successfully Updated [%s] users', 1)
        self._assert_superusers(expected_count=0)

    def test_no_superuser(self):
        """
        Tests that the management command successfully falls back when
        the system does not has any superusers.
        """
        call_command(self.command)
        self._assert_superusers(expected_count=0)

        with mock.patch(self.LOGGER) as patched_log:
            call_command(self.command)
            patched_log.warning.assert_called_once_with('No superusers found, falling back.')

    def test_superuser_factory_lms_user_id(self):
        """
        Test that the SuperUserFactory creates users with an LMS user id.
        """
        user = User.objects.filter(is_superuser=True).first()
        self.assertIsNotNone(user.lms_user_id)
        self.assertEqual(SuperUserFactory.lms_user_id, user.lms_user_id)
