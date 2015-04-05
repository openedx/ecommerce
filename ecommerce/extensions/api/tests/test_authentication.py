import json
from django.conf import settings

from django.test import TestCase, override_settings, RequestFactory
import httpretty
from oscar.test import factories
from rest_framework.exceptions import AuthenticationFailed

from ecommerce.extensions.api.authentication import BearerAuthentication


OAUTH2_PROVIDER_URL = 'https://example.com/oauth2'


class AccessTokenMixin(object):
    DEFAULT_TOKEN = 'abc123'

    def _mock_access_token_response(self, status=200, token=DEFAULT_TOKEN, username='fake-user'):
        httpretty.register_uri(httpretty.GET, '{}/access_token/{}/'.format(OAUTH2_PROVIDER_URL, token),
                               body=json.dumps({'username': username, 'scope': 'read', 'expires_in': 60}),
                               content_type="application/json",
                               status=status)


@override_settings(OAUTH2_PROVIDER_URL=OAUTH2_PROVIDER_URL)
class BearerAuthenticationTests(AccessTokenMixin, TestCase):
    def setUp(self):
        super(BearerAuthenticationTests, self).setUp()
        self.auth = BearerAuthentication()
        self.factory = RequestFactory()

    def _create_request(self, token=AccessTokenMixin.DEFAULT_TOKEN, token_name='Bearer'):
        auth_header = '{} {}'.format(token_name, token)
        request = self.factory.get('/', HTTP_AUTHORIZATION=auth_header)
        return request

    def test_authenticate_header(self):
        """ The method should return the string Bearer. """
        self.assertEqual(self.auth.authenticate_header(self._create_request()), 'Bearer')

    @override_settings(OAUTH2_PROVIDER_URL=None)
    def test_authenticate_no_provider(self):
        """ If the setting OAUTH2_PROVIDER_URL is not set, the method returns None. """

        # Empty value
        self.assertIsNone(self.auth.authenticate(self._create_request()))

        # Missing value
        del settings.OAUTH2_PROVIDER_URL
        self.assertIsNone(self.auth.authenticate(self._create_request()))

    def test_authenticate_invalid_token(self):
        """ If no token is supplied, or if the token contains spaces, the method should raise an exception. """

        # Missing token
        request = self._create_request('')
        self.assertRaises(AuthenticationFailed, self.auth.authenticate, request)

        # Token with spaces
        request = self._create_request('abc 123 456')
        self.assertRaises(AuthenticationFailed, self.auth.authenticate, request)

    def test_authenticate_invalid_token_name(self):
        """ If the token name is not Bearer, the method should return None. """
        request = self._create_request(token_name='foobar')
        self.assertIsNone(self.auth.authenticate(request))

    @httpretty.activate
    def test_authenticate_missing_user(self):
        """ If the user matching the access token does not exist, the method should raise an exception. """
        self._mock_access_token_response()
        request = self._create_request()

        self.assertRaises(AuthenticationFailed, self.auth.authenticate, request)

    @httpretty.activate
    def test_authenticate_inactive_user(self):
        """ If the user matching the access token is inactive, the method should raise an exception. """
        user = factories.UserFactory(is_active=False)

        self._mock_access_token_response(username=user.username)

        request = self._create_request()
        self.assertRaises(AuthenticationFailed, self.auth.authenticate, request)

    @httpretty.activate
    def test_authenticate_invalid_token_response(self):
        """ If the OAuth2 provider does not return HTTP 200, the method should return raise an exception. """
        self._mock_access_token_response(status=400)
        request = self._create_request()
        self.assertRaises(AuthenticationFailed, self.auth.authenticate, request)

    @httpretty.activate
    def test_authenticate(self):
        """
        If the access token is valid, the user exists, and is active, a tuple containing
        the user and token should be returned.
        """
        user = factories.UserFactory()
        self._mock_access_token_response(username=user.username)

        request = self._create_request()
        self.assertEqual(self.auth.authenticate(request), (user, self.DEFAULT_TOKEN))
