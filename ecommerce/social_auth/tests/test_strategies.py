"""Tests of social auth strategies."""


import datetime
import json
import re
import uuid
from calendar import timegm

import httpretty
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from jwkest.jwk import SYMKey
from jwkest.jws import JWS
from social_django.models import DjangoStorage

from ecommerce.social_auth.strategies import CurrentSiteDjangoStrategy
from ecommerce.tests.testcases import TestCase

User = get_user_model()

CONTENT_TYPE = 'application/json'


class CurrentSiteDjangoStrategyTests(TestCase):
    """Tests of the CurrentSiteDjangoStrategy."""

    def setUp(self):
        super(CurrentSiteDjangoStrategyTests, self).setUp()
        self.strategy = CurrentSiteDjangoStrategy(DjangoStorage, self.request)

    def test_get_setting_from_siteconfiguration(self):
        """Test that a setting can be retrieved from the site configuration."""
        setting_name = 'SOCIAL_AUTH_EDX_OAUTH2_KEY'
        expected = str(uuid.uuid4())
        self.site.siteconfiguration.oauth_settings[setting_name] = expected
        self.site.siteconfiguration.save()

        self.assertEqual(self.strategy.get_setting(setting_name), expected)

    def test_get_setting_from_django_settings(self):
        """Test that a setting can be retrieved from django settings if it doesn't exist in site configuration."""
        setting_name = 'SOCIAL_AUTH_EDX_OAUTH2_SECRET'
        expected = str(uuid.uuid4())

        if setting_name in self.site.siteconfiguration.oauth_settings:
            del self.site.siteconfiguration.oauth_settings[setting_name]
            self.site.siteconfiguration.save()

        with override_settings(**{setting_name: expected}):
            self.assertEqual(self.strategy.get_setting(setting_name), expected)

    def test_get_setting_raises_exception_on_missing_setting(self):
        """Test that a setting that does not exist raises exception."""
        with self.assertRaises(KeyError):
            self.strategy.get_setting('FAKE_SETTING')

    def create_jwt(self, user):
        """
        Creates a signed (JWS) ID token.

        Returns:
            str: JWS
        """
        key = SYMKey(key=self.site.siteconfiguration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_SECRET'])
        now = datetime.datetime.utcnow()
        expiration_datetime = now + datetime.timedelta(seconds=3600)
        issue_datetime = now
        payload = {
            'iss': self.site.siteconfiguration.lms_url_root,
            'administrator': False,
            'iat': timegm(issue_datetime.utctimetuple()),
            'sub': str(uuid.uuid4()),
            'preferred_username': user.username,
            'aud': self.site.siteconfiguration.oauth_settings['SOCIAL_AUTH_EDX_OAUTH2_KEY'],
            'exp': timegm(expiration_datetime.utctimetuple()),
        }
        access_token = JWS(payload, jwk=key, alg='HS512').sign_compact()
        return access_token

    def mock_access_token_jwt_response(self, user, status=200):
        """ Mock the response from the OAuth provider's access token endpoint. """
        assert httpretty.is_enabled(), 'httpretty must be enabled to mock the access token response.'

        # Use a regex to account for the optional trailing slash
        url = '{root}/access_token/?'.format(root=self.site.siteconfiguration.oauth2_provider_url)
        url = re.compile(url)

        token = self.create_jwt(user)
        data = {
            'access_token': token,
            'expires_in': 3600,
        }
        body = json.dumps(data)
        httpretty.register_uri(httpretty.POST, url, body=body, content_type=CONTENT_TYPE, status=status)

        return token

    @httpretty.activate
    def test_authentication(self):
        """ Returning users should be able to re-authenticate to the same acccount, rather than get a new account with
        a UUID. This validates the fix made by https://github.com/python-social-auth/social-core/pull/74.
        """
        self.site.siteconfiguration.oauth_settings = {
            'SOCIAL_AUTH_EDX_OAUTH2_KEY': 'test-key',
            'SOCIAL_AUTH_EDX_OAUTH2_SECRET': 'test-secret',
            'SOCIAL_AUTH_EDX_OAUTH2_URL_ROOT': self.site.siteconfiguration.lms_url_root,
            'SOCIAL_AUTH_EDX_OAUTH2_ISSUER': self.site.siteconfiguration.lms_url_root,

        }
        self.site.siteconfiguration.save()

        # Remove all users to ensure a clean test environment
        User.objects.all().delete()

        # Create an existing user for which we will need to make a new social auth account association
        user = self.create_user()
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(user.social_auth.count(), 0)

        # Mock access token endpoint so that it returns an ID token
        self.mock_access_token_jwt_response(user)

        # Simulate login completion
        state = str(uuid.uuid4())
        session = self.client.session
        session['edx-oauth2_state'] = state
        session.save()
        url = '{host}?state={state}'.format(host=reverse('social:complete', args=['edx-oauth2']), state=state)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        # Verify a new account is NOT created, and the new user has a social auth account association.
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(user.social_auth.count(), 1)
