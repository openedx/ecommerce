# -*- coding: utf-8 -*-
from datetime import datetime
import json
from logging import Logger

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.conf.urls import url
from django.test import override_settings, RequestFactory
import httpretty
import mock
from oscar.test import factories
from rest_framework import permissions
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.views import APIView
from rest_framework_jwt import utils

from ecommerce.core.url_utils import get_oauth2_provider_url
from ecommerce.extensions.api.authentication import BearerAuthentication, JwtAuthentication
from ecommerce.tests.mixins import JwtMixin
from ecommerce.tests.testcases import TestCase

User = get_user_model()


class MockView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):  # pylint: disable=unused-variable, unused-argument
        return HttpResponse()


urlpatterns = [
    url(r'^jwt/$', MockView.as_view(authentication_classes=[JwtAuthentication]))
]


class AccessTokenMixin(object):
    DEFAULT_TOKEN = 'abc123'

    def _mock_access_token_response(self, status=200, token=DEFAULT_TOKEN, username='fake-user'):
        httpretty.register_uri(httpretty.GET, '{}/access_token/{}/'.format(get_oauth2_provider_url(), token),
                               body=json.dumps({'username': username, 'scope': 'read', 'expires_in': 60}),
                               content_type="application/json",
                               status=status)


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

    @mock.patch('ecommerce.core.url_utils.get_lms_url', mock.Mock(return_value=None))
    def test_authenticate_no_provider(self):
        """ If the we cannot get the LMS URL, the method returns None. """
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


@override_settings(
    ROOT_URLCONF='ecommerce.extensions.api.tests.test_authentication',
)
class JwtAuthenticationTests(JwtMixin, TestCase):
    def assert_jwt_status(self, issuer=None, expires=None, status_code=200):
        """Assert that the payload has a valid issuer and has not expired."""
        staff_user = self.create_user(is_staff=True)
        issuer = issuer or settings.JWT_AUTH['JWT_ISSUERS'][0]

        payload = {
            'iss': issuer,
            'username': staff_user.username,
            'email': staff_user.email,
            'full_name': staff_user.full_name
        }

        if expires:
            payload['exp'] = expires

        token = utils.jwt_encode_handler(payload)

        auth = 'JWT {0}'.format(token)
        response = self.client.get('/jwt/', HTTP_AUTHORIZATION=auth)

        self.assertEqual(response.status_code, status_code)

    def test_valid_issuer(self):
        """ Verify payloads with valid issuers are validated. """
        self.assert_jwt_status()

    def test_invalid_issuer(self):
        """ Verify payloads with invalid issuers are NOT validated. """
        self.assert_jwt_status(issuer='some-invalid-issuer', status_code=401)

    def test_valid_expiration(self):
        """ Verify payloads with valid expiration dates are validated. """
        valid_timestamp = int(datetime.max.strftime('%s'))
        self.assert_jwt_status(expires=valid_timestamp)

    def test_invalid_expiration(self):
        """ Verify payloads with invalid expiration dates are NOT validated. """
        self.assert_jwt_status(expires=1, status_code=401)

    def test_authenticate_credentials_user_creation(self):
        """ Test whether the user model is being assigned fields from the payload. """

        full_name = 'Ｇｅｏｒｇｅ Ｃｏｓｔａｎｚａ'
        email = 'gcostanza@gmail.com'
        username = 'gcostanza'

        payload = {'username': username, 'email': email, 'full_name': full_name}
        user = JwtAuthentication().authenticate_credentials(payload)
        self.assertEquals(user.username, username)
        self.assertEquals(user.email, email)
        self.assertEquals(user.full_name, full_name)

    def test_user_retrieval_failed(self):
        """ Verify exceptions raised during user retrieval are properly logged. """

        with mock.patch.object(User.objects, 'get_or_create', side_effect=ValueError):
            with mock.patch.object(Logger, 'exception') as logger:
                msg = 'User retrieval failed.'
                with self.assertRaisesRegexp(AuthenticationFailed, msg):
                    payload = {'username': 'test', 'email': 'test@example.com', 'full_name': 'Testy'}
                    JwtAuthentication().authenticate_credentials(payload)

                logger.assert_called_with(msg)
