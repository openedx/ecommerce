"""Tests of the service health endpoint."""


import mock
from django.conf import settings
from django.contrib.auth import get_user, get_user_model
from django.db import DatabaseError
from django.test.utils import override_settings
from django.urls import reverse
from rest_framework import status
from social_django.models import UserSocialAuth

from ecommerce.core.constants import Status
from ecommerce.core.views import AutoAuth
from ecommerce.tests.factories import UserFactory
from ecommerce.tests.testcases import TestCase

LOGGER_NAME = 'ecommerce.core.views'
User = get_user_model()


class HealthTests(TestCase):
    """Tests of the health endpoint."""

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
        self.assertDictEqual(response.json(), expected_data)


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

        # Verify that a redirect has occurred and that a new user has been created
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), original_user_count + 1)

        # Get the latest user
        user = User.objects.latest()

        # Verify that the user is logged in and that their username has the expected prefix
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertTrue(user.username.startswith(settings.AUTO_AUTH_USERNAME_PREFIX))

        # Verify that the user has superuser permissions
        self.assertTrue(user.is_superuser)

        # Verify that the user has an LMS user id
        self.assertIsNotNone(user.lms_user_id)
        self.assertEqual(AutoAuth.lms_user_id, user.lms_user_id)


class LogoutViewTests(TestCase):
    """ Taken from https://github.com/edx/auth-backends/blob/master/auth_backends/tests/mixins.py """
    PASSWORD = 'test'

    def _create_user(self):
        """ Create a new user. """
        user = UserFactory(username='test', password=self.PASSWORD)
        UserSocialAuth.objects.create(user=user, provider='edx-oauth2', uid=user.username)
        return user

    def get_logout_url(self):
        """ Returns the URL of the logout view. """
        return reverse('logout')

    def get_redirect_url(self):
        return self.site.siteconfiguration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_LOGOUT_URL']

    def assert_authentication_status(self, is_authenticated):
        """ Verifies the authentication status of the user attached to the test client. """
        user = get_user(self.client)
        self.assertEqual(user.is_authenticated, is_authenticated)

    def test_x_frame_options_header(self):
        """ Verify no X-Frame-Options header is set in the response. """
        response = self.client.get(self.get_logout_url())
        self.assertNotIn('X-Frame-Options', response)

    def test_logout(self):
        """ Verify the user is logged out of the current session and redirected to the appropriate URL. """
        self.client.logout()
        self.assert_authentication_status(False)

        user = self._create_user()
        self.client.login(username=user.username, password=self.PASSWORD)
        self.assert_authentication_status(True)

        qs = 'next=/test/'
        response = self.client.get('{url}?{qs}'.format(url=self.get_logout_url(), qs=qs))
        self.assert_authentication_status(False)

        # NOTE: The querystring parameters SHOULD be ignored
        self.assertRedirects(response, self.get_redirect_url(), fetch_redirect_response=False)

    def test_no_redirect(self):
        """ Verify the view does not redirect if the no_redirect querystring parameter is set. """
        response = self.client.get(self.get_logout_url(), {'no_redirect': 1})
        self.assertEqual(response.status_code, 200)
