"""Tests of social auth strategies."""
import datetime
import uuid
from calendar import timegm

import httpretty
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.test import override_settings
from jwkest.jwk import SYMKey
from jwkest.jws import JWS
from social_django.models import DjangoStorage

from ecommerce.social_auth.strategies import CurrentSiteDjangoStrategy
from ecommerce.tests.testcases import TestCase

User = get_user_model()


class CurrentSiteDjangoStrategyTests(TestCase):
    """Tests of the CurrentSiteDjangoStrategy."""

    def setUp(self):
        super(CurrentSiteDjangoStrategyTests, self).setUp()
        self.strategy = CurrentSiteDjangoStrategy(DjangoStorage, self.request)

    def test_get_setting_from_siteconfiguration(self):
        """Test that a setting can be retrieved from the site configuration."""
        setting_name = 'SOCIAL_AUTH_EDX_OIDC_KEY'
        expected = str(uuid.uuid4())
        self.site.siteconfiguration.oauth_settings[setting_name] = expected
        self.site.siteconfiguration.save()

        self.assertEqual(self.strategy.get_setting(setting_name), expected)

    def test_get_setting_from_django_settings(self):
        """Test that a setting can be retrieved from django settings if it doesn't exist in site configuration."""
        setting_name = 'SOCIAL_AUTH_EDX_OIDC_SECRET'
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

    def create_id_token(self, user):
        """
        Creates a signed (JWS) ID token.

        Returns:
            str: JWS
        """
        key = SYMKey(key=self.site.siteconfiguration.oauth_settings['SOCIAL_AUTH_EDX_OIDC_SECRET'])
        now = datetime.datetime.utcnow()
        expiration_datetime = now + datetime.timedelta(seconds=3600)
        issue_datetime = now
        payload = {
            'iss': self.site.siteconfiguration.oauth2_provider_url,
            'administrator': False,
            'iat': timegm(issue_datetime.utctimetuple()),
            'given_name': user.first_name,
            'sub': str(uuid.uuid4()),
            'preferred_username': user.username,
            'aud': self.site.siteconfiguration.oauth_settings['SOCIAL_AUTH_EDX_OIDC_KEY'],
            'email': user.email,
            'exp': timegm(expiration_datetime.utctimetuple()),
            'name': user.get_full_name(),
            'family_name': user.last_name,
        }
        access_token = JWS(payload, jwk=key, alg='HS512').sign_compact()
        return access_token

    @httpretty.activate
    def test_authentication(self):
        """ Returning users should be able to re-authenticate to the same acccount, rather than get a new account with
        a UUID. This validates the fix made by https://github.com/python-social-auth/social-core/pull/74.
        """
        self.site.siteconfiguration.oauth_settings = {
            'SOCIAL_AUTH_EDX_OIDC_KEY': 'test-key',
            'SOCIAL_AUTH_EDX_OIDC_SECRET': 'test-secret',
            'SOCIAL_AUTH_EDX_OIDC_URL_ROOT': self.site.siteconfiguration.oauth2_provider_url,
            'SOCIAL_AUTH_EDX_OIDC_ID_TOKEN_DECRYPTION_KEY': 'test-secret',
            'SOCIAL_AUTH_EDX_OIDC_ISSUER': self.site.siteconfiguration.oauth2_provider_url,

        }
        self.site.siteconfiguration.save()

        # Remove all users to ensure a clean test environment
        User.objects.all().delete()

        # Create an existing user for which we will need to make a new social auth account association
        user = self.create_user()
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(user.social_auth.count(), 0)

        # Mock access token endpoint so that it returns an ID token
        id_token = self.create_id_token(user)
        self.mock_access_token_response(id_token=id_token)

        # Simulate login completion
        state = str(uuid.uuid4())
        session = self.client.session
        session['edx-oidc_state'] = state
        session.save()
        url = '{host}?state={state}'.format(host=reverse('social:complete', args=['edx-oidc']), state=state)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)

        # Verify a new account is NOT created, and the new user has a social auth account association.
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(user.social_auth.count(), 1)
