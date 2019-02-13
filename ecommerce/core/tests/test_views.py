"""Tests of the service health endpoint."""
import json

import mock
from auth_backends.tests.mixins import LogoutViewTestMixin
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test.utils import override_settings
from django.urls import reverse
from rest_framework import status

from ecommerce.core.constants import Status
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.core.views'
User = get_user_model()


class HealthTests(TestCase):
    """Tests of the health endpoint."""

    def setUp(self):
        super(HealthTests, self).setUp()

    def test_all_services_available(self):
        """Test that the endpoint reports when all services are healthy."""
        self._assert_health(status.HTTP_200_OK, Status.OK, Status.OK)

    @mock.patch('newrelic.agent')
    def test_health_check_is_ignored_by_new_relic(self, mock_newrelic_agent):
        """Test that the health endpoint is ignored by NewRelic"""
        self._assert_health(status.HTTP_200_OK, Status.OK, Status.OK)
        self.assertTrue(mock_newrelic_agent.ignore_transaction.called)

    @mock.patch('django.contrib.sites.middleware.get_current_site', mock.Mock(return_value=None))
    @mock.patch('django.db.backends.base.base.BaseDatabaseWrapper.cursor', mock.Mock(side_effect=DatabaseError))
    def test_database_outage(self):
        """Test that the endpoint reports when the database is unavailable."""
        self._assert_health(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            Status.UNAVAILABLE,
            Status.UNAVAILABLE,
        )

    def _assert_health(self, status_code, overall_status, database_status):
        """Verify that the response matches expectations."""
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, status_code)
        self.assertEqual(response['content-type'], 'application/json')

        expected_data = {
            'overall_status': overall_status,
            'detailed_status': {
                'database_status': database_status,
            }
        }
        self.assertDictEqual(json.loads(response.content), expected_data)


class AutoAuthTests(TestCase):
    AUTO_AUTH_PATH = reverse('auto_auth')

    @override_settings(ENABLE_AUTO_AUTH=False)
    def test_setting_disabled(self):
        """When the ENABLE_AUTO_AUTH setting is False, the view should raise a 404."""
        response = self.client.get(self.AUTO_AUTH_PATH)
        self.assertEqual(response.status_code, 404)

    @override_settings(ENABLE_AUTO_AUTH=True)
    def test_setting_enabled(self):
        """
        When ENABLE_AUTO_AUTH is set to True, the view should create and authenticate
        a new User with superuser permissions.
        """
        original_user_count = User.objects.count()
        response = self.client.get(self.AUTO_AUTH_PATH)

        # Verify that a redirect has occured and that a new user has been created
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), original_user_count + 1)

        # Get the latest user
        user = User.objects.latest()

        # Verify that the user is logged in and that their username has the expected prefix
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertTrue(user.username.startswith(settings.AUTO_AUTH_USERNAME_PREFIX))

        # Verify that the user has superuser permissions
        self.assertTrue(user.is_superuser)


class LogoutViewTests(LogoutViewTestMixin, TestCase):
    def get_redirect_url(self):
        return self.site.siteconfiguration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_LOGOUT_URL']
