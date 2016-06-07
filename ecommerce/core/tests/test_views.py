"""Tests of the service health endpoint."""
import json

import mock
from auth_backends.tests.mixins import LogoutViewTestMixin
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.db import DatabaseError
from django.test.utils import override_settings
from requests import Response
from requests.exceptions import RequestException
from rest_framework import status
from testfixtures import LogCapture

from ecommerce.core.constants import Status, UnavailabilityMessage
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.core.views'
User = get_user_model()


@mock.patch('requests.get')
class HealthTests(TestCase):
    """Tests of the health endpoint."""

    def setUp(self):
        super(HealthTests, self).setUp()
        self.fake_lms_response = Response()

    def test_all_services_available(self, mock_lms_request):
        """Test that the endpoint reports when all services are healthy."""
        self.fake_lms_response.status_code = status.HTTP_200_OK
        mock_lms_request.return_value = self.fake_lms_response

        self._assert_health(status.HTTP_200_OK, Status.OK, Status.OK, Status.OK)

    @mock.patch('ecommerce.core.views.get_lms_heartbeat_url', mock.Mock(return_value=''))
    @mock.patch('django.contrib.sites.middleware.get_current_site', mock.Mock(return_value=None))
    @mock.patch('django.db.backends.base.base.BaseDatabaseWrapper.cursor', mock.Mock(side_effect=DatabaseError))
    def test_database_outage(self, mock_lms_request):
        """Test that the endpoint reports when the database is unavailable."""
        self.fake_lms_response.status_code = status.HTTP_200_OK
        mock_lms_request.return_value = self.fake_lms_response

        self._assert_health(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            Status.UNAVAILABLE,
            Status.UNAVAILABLE,
            Status.OK
        )

    def test_lms_outage(self, mock_lms_request):
        """Test that the endpoint reports when the LMS is unhealthy."""
        self.fake_lms_response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        mock_lms_request.return_value = self.fake_lms_response

        with LogCapture(LOGGER_NAME) as l:
            self._assert_health(
                status.HTTP_200_OK,
                Status.OK,
                Status.OK,
                Status.UNAVAILABLE
            )
            l.check((LOGGER_NAME, 'CRITICAL', UnavailabilityMessage.LMS))

    def test_lms_connection_failure(self, mock_lms_request):
        """Test that the endpoint reports when it cannot contact the LMS."""
        mock_lms_request.side_effect = RequestException

        with LogCapture(LOGGER_NAME) as l:
            self._assert_health(
                status.HTTP_200_OK,
                Status.OK,
                Status.OK,
                Status.UNAVAILABLE
            )
            l.check((LOGGER_NAME, 'CRITICAL', UnavailabilityMessage.LMS))

    def _assert_health(self, status_code, overall_status, database_status, lms_status):
        """Verify that the response matches expectations."""
        response = self.client.get(reverse('health'))
        self.assertEqual(response.status_code, status_code)
        self.assertEqual(response['content-type'], 'application/json')

        expected_data = {
            'overall_status': overall_status,
            'detailed_status': {
                'database_status': database_status,
                'lms_status': lms_status
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
        return self.site.siteconfiguration.build_lms_url('logout')
