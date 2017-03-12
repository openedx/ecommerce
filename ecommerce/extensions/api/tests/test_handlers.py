""" Tests for handler functions. """
from time import time

import jwt
import mock
from django.conf import settings
from django.test import TestCase
from oscar.test.factories import UserFactory

from ecommerce.extensions.api.handlers import jwt_decode_handler

ISSUERS = ('test-issuer', 'another-issuer',)
SIGNING_KEYS = ('insecure-secret-key', 'secret', 'another-secret',)


def generate_jwt_token(payload, signing_key=None):
    """Generate a valid JWT token for authenticated requests."""
    signing_key = signing_key or settings.JWT_AUTH['JWT_SECRET_KEY']
    return jwt.encode(payload, signing_key).decode('utf-8')


def generate_jwt_payload(user):
    """Generate a valid JWT payload given a user."""
    now = int(time())
    ttl = 5
    return {
        'iss': settings.JWT_AUTH['JWT_ISSUERS'][0],
        'username': user.username,
        'email': user.email,
        'iat': now,
        'exp': now + ttl
    }


class JWTDecodeHandlerTests(TestCase):
    """ Tests for the `jwt_decode_handler` utility function. """

    def setUp(self):
        super(JWTDecodeHandlerTests, self).setUp()
        self.user = UserFactory()
        self.payload = generate_jwt_payload(self.user)
        self.jwt = generate_jwt_token(self.payload)

    def test_decode_success(self):
        self.assertEqual(jwt_decode_handler(self.jwt), self.payload)

    def test_decode_success_with_multiple_issuers(self):
        settings.JWT_AUTH['JWT_ISSUERS'] = ISSUERS

        for issuer in ISSUERS:
            self.payload['iss'] = issuer
            token = generate_jwt_token(self.payload)
            self.assertEqual(jwt_decode_handler(token), self.payload)

    def test_decode_success_with_multiple_signing_keys(self):
        settings.JWT_AUTH['JWT_SECRET_KEYS'] = SIGNING_KEYS

        for signing_key in SIGNING_KEYS:
            token = generate_jwt_token(self.payload, signing_key)
            self.assertEqual(jwt_decode_handler(token), self.payload)

    def test_decode_error(self):
        # Update the payload to ensure a validation error
        self.payload['exp'] = 0
        token = generate_jwt_token(self.payload)

        with mock.patch('ecommerce.extensions.api.handlers.logger') as patched_log:
            with self.assertRaises(jwt.InvalidTokenError):
                jwt_decode_handler(token)

            patched_log.exception.assert_called_once_with('JWT decode failed!')
